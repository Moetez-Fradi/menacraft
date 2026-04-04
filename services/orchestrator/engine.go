package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"
)

const globalTimeout = 15 * time.Second // CPU inference + Wikipedia lookup; axes run in parallel

// ---- downstream service URLs (overridable via env) ----

var (
	mlServiceURL    = envOr("ML_SERVICE_URL", "http://ml-engine:8082")
	truthServiceURL = envOr("TRUTH_SERVICE_URL", "http://truth-service:8083")
)

// ---- axis result types ----

type AxisClassifier struct {
	Category   string   `json:"category"`
	Confidence float64  `json:"confidence"`
	Highlights []string `json:"highlights"`
	Reasoning  string   `json:"reasoning"`
	IsNews     bool     `json:"is_news"`
}

type AxisContext struct {
	IsMisleading bool    `json:"is_misleading"`
	Confidence   float64 `json:"confidence"`
	Explanation  string  `json:"explanation"`
}

type AxisSource struct {
	CredibilityScore float64  `json:"credibility_score"`
	RiskLevel        string   `json:"risk_level"`
	Signals          []string `json:"signals"`
}

type AxisTruth struct {
	IsNews           bool     `json:"is_news"`
	IsMisinformation bool     `json:"is_misinformation"`
	Confidence       float64  `json:"confidence"`
	Verdict          string   `json:"verdict"`
	Explanation      string   `json:"explanation"`
	CorrectedVersion string   `json:"corrected_version"`
	Sources          []Source `json:"sources"`
}

type Source struct {
	Title string `json:"title"`
	URL   string `json:"url"`
}

// ---- orchestration result ----

type EngineResult struct {
	ThreatLevel float64 `json:"threat_level"`
	Verdict     string  `json:"verdict"`
	Axes        struct {
		Classifier *AxisClassifier `json:"classifier,omitempty"`
		Context    *AxisContext    `json:"context,omitempty"`
		Source     *AxisSource     `json:"source,omitempty"`
		Truth      *AxisTruth      `json:"truth,omitempty"`
	} `json:"axes"`
	LatencyMS int64 `json:"latency_ms"`
}

// AnalyzeRequest is the unified payload handed to the engine after anonymization.
type AnalyzeRequest struct {
	SessionID     string                 `json:"session_id"`
	CleanText     string                 `json:"clean_text"`
	RawText       string                 `json:"raw_text,omitempty"` // pre-anonymization, used for truth search only
	CleanImageB64 string                 `json:"clean_image_base64,omitempty"`
	ContentType   string                 `json:"content_type"`
	Metadata      map[string]interface{} `json:"metadata"`
}

// looksLikeNews is a fast text heuristic to decide whether to fan out axis 4
// without waiting for the ML classifier result.
func looksLikeNews(text string) bool {
	newsKW := []string{
		"breaking", "exclusive", "report", "president", "minister",
		"attack", "killed", "war", "crisis", "government", "official",
		"election", "court", "police", "military", "announced", "confirmed",
		"according to", "sources say", "just in", "developing",
	}
	lower := text
	count := 0
	for _, kw := range newsKW {
		if len(lower) > 0 && containsFold(lower, kw) {
			count++
			if count >= 2 {
				return true
			}
		}
	}
	return false
}

func containsFold(s, sub string) bool {
	sLen, subLen := len(s), len(sub)
	if subLen > sLen {
		return false
	}
	for i := 0; i <= sLen-subLen; i++ {
		match := true
		for j := 0; j < subLen; j++ {
			c1, c2 := s[i+j], sub[j]
			if c1 >= 'A' && c1 <= 'Z' {
				c1 += 32
			}
			if c1 != c2 {
				match = false
				break
			}
		}
		if match {
			return true
		}
	}
	return false
}

// Run fans out to all axes in parallel and aggregates the result.
// All four axes start concurrently; axis 4 result is used only when text looks like news.
func Run(req AnalyzeRequest) EngineResult {
	start := time.Now()
	ctx, cancel := context.WithTimeout(context.Background(), globalTimeout)
	defer cancel()

	type classifierResult struct {
		val *AxisClassifier
		err error
	}
	type contextResult struct {
		val *AxisContext
		err error
	}
	type sourceResult struct {
		val *AxisSource
		err error
	}
	type truthResult struct {
		val *AxisTruth
		err error
	}

	clCh  := make(chan classifierResult, 1)
	ctxCh := make(chan contextResult, 1)
	srcCh := make(chan sourceResult, 1)
	trCh  := make(chan truthResult, 1)

	// Axes 1 + 2 hit the ML engine (CPU-bound, run in parallel)
	go func() {
		v, err := callClassifier(ctx, req)
		clCh <- classifierResult{v, err}
	}()
	go func() {
		v, err := callContext(ctx, req)
		ctxCh <- contextResult{v, err}
	}()
	// Axis 3 hits the truth/intelligence service
	go func() {
		v, err := callSource(ctx, req)
		srcCh <- sourceResult{v, err}
	}()
	// Axis 4: start in parallel using a fast local heuristic to skip irrelevant content
	maybeNews := looksLikeNews(req.CleanText)
	go func() {
		if !maybeNews {
			trCh <- truthResult{}
			return
		}
		v, err := callTruth(ctx, req)
		trCh <- truthResult{v, err}
	}()

	clRes  := <-clCh
	ctxRes := <-ctxCh
	srcRes := <-srcCh
	trRes  := <-trCh

	if clRes.err != nil {
		log.Printf("axis1 error: %v", clRes.err)
	}
	if ctxRes.err != nil {
		log.Printf("axis2 error: %v", ctxRes.err)
	}
	if srcRes.err != nil {
		log.Printf("axis3 error: %v", srcRes.err)
	}
	if trRes.err != nil {
		log.Printf("axis4 error: %v", trRes.err)
	}

	// isNews: trust ML classifier if available, fall back to heuristic
	isNews := maybeNews
	if clRes.val != nil {
		isNews = clRes.val.IsNews
	}

	result := EngineResult{LatencyMS: time.Since(start).Milliseconds()}
	result.Axes.Classifier = clRes.val
	result.Axes.Context = ctxRes.val
	result.Axes.Source = srcRes.val
	if isNews {
		result.Axes.Truth = trRes.val
	}

	result.ThreatLevel = aggregate(clRes.val, ctxRes.val, srcRes.val, trRes.val, isNews)
	result.Verdict = toVerdict(result.ThreatLevel)

	return result
}

// aggregate computes a weighted threat score.
// Weights: Axis1(classifier)=0.20, Axis2(context)=0.25, Axis3(source)=0.15, Axis4(truth)=0.40
// Context (axis2) gets a higher weight than classifier because the AI detector only catches
// AI-generated text — human-written misinformation flows through context + truth axes instead.
func aggregate(cl *AxisClassifier, ct *AxisContext, src *AxisSource, tr *AxisTruth, isNews bool) float64 {
	var w1, w2, w3, w4 float64 = 0.20, 0.25, 0.15, 0.40

	if !isNews {
		// Redistribute axis 4 weight proportionally
		total := w1 + w2 + w3
		w1 = w1 / total
		w2 = w2 / total
		w3 = w3 / total
		w4 = 0
	}

	var score float64

	if cl != nil {
		s := 0.0
		switch cl.Category {
		case "ai_generated":
			// Scale confidence (0.5–1.0) into threat range (0.5–1.0)
			s = 0.5 + cl.Confidence*0.5
		case "altered":
			// Scale confidence into range (0.35–0.80)
			s = 0.35 + cl.Confidence*0.45
		default:
			s = 0.05
		}
		if s > 1.0 {
			s = 1.0
		}
		score += w1 * s
	}

	if ct != nil {
		s := 0.0
		if ct.IsMisleading {
			s = ct.Confidence
		}
		score += w2 * s
	}

	if src != nil {
		s := 1.0 - src.CredibilityScore
		score += w3 * s
	}

	if tr != nil && isNews {
		s := 0.0
		if tr.IsMisinformation {
			s = tr.Confidence
		}
		score += w4 * s
	}

	if score > 1.0 {
		score = 1.0
	}
	return score
}

func toVerdict(score float64) string {
	switch {
	case score < 0.35:
		return "REAL"
	case score < 0.65:
		return "SUSPICIOUS"
	default:
		return "FAKE"
	}
}

// ---- HTTP helpers ----

func post(ctx context.Context, url string, body interface{}, out interface{}) error {
	data, err := json.Marshal(body)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("upstream %d: %s", resp.StatusCode, string(b))
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

func callClassifier(ctx context.Context, req AnalyzeRequest) (*AxisClassifier, error) {
	var out AxisClassifier
	err := post(ctx, mlServiceURL+"/classify", req, &out)
	if err != nil {
		return nil, err
	}
	return &out, nil
}

func callContext(ctx context.Context, req AnalyzeRequest) (*AxisContext, error) {
	var out AxisContext
	err := post(ctx, mlServiceURL+"/context", req, &out)
	if err != nil {
		return nil, err
	}
	return &out, nil
}

func callSource(ctx context.Context, req AnalyzeRequest) (*AxisSource, error) {
	var out AxisSource
	err := post(ctx, truthServiceURL+"/source", req, &out)
	if err != nil {
		return nil, err
	}
	return &out, nil
}

func callTruth(ctx context.Context, req AnalyzeRequest) (*AxisTruth, error) {
	// Use original (pre-anonymization) text for truth search so proper nouns
	// (place names, people, events) aren't stripped and Wikipedia returns useful results.
	truthReq := req
	if req.RawText != "" {
		truthReq.CleanText = req.RawText
	}
	var out AxisTruth
	err := post(ctx, truthServiceURL+"/truth", truthReq, &out)
	if err != nil {
		return nil, err
	}
	return &out, nil
}
