package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/google/uuid"
)

// SessionID generates a privacy-safe session ID: UUID + timestamp hash.
// No IP or identity is encoded.
func NewSessionID() string {
	id := uuid.New().String()
	ts := fmt.Sprintf("%d", time.Now().UnixNano())
	hash := sha256.Sum256([]byte(id + ts))
	return id + "-" + hex.EncodeToString(hash[:4])
}

// AnonymizedPayload is the clean-room output contract.
type AnonymizedPayload struct {
	SessionID       string                 `json:"session_id"`
	CleanText       string                 `json:"clean_text"`
	CleanImageB64   string                 `json:"clean_image_base64,omitempty"`
	ContentType     string                 `json:"content_type"` // text|image|video|audio|account
	Metadata        map[string]interface{} `json:"metadata"`
}

// AnonymizeRequest holds the raw inbound data.
type AnonymizeRequest struct {
	Text        string                 `json:"text"`
	ImageB64    string                 `json:"image_base64"`
	ContentType string                 `json:"content_type"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// Process routes the request through the correct anonymizer and returns
// a clean payload. No raw data is stored.
func Process(req AnonymizeRequest) (AnonymizedPayload, error) {
	out := AnonymizedPayload{
		SessionID:   NewSessionID(),
		ContentType: req.ContentType,
		Metadata:    make(map[string]interface{}),
	}

	// Always anonymize text regardless of content type
	if req.Text != "" {
		out.CleanText = AnonymizeText(req.Text)
	}

	// Image anonymization
	if req.ImageB64 != "" {
		clean, err := StripAndAnonymizeImage(req.ImageB64)
		if err != nil {
			// Don't fail the whole request; just mark the image as unavailable
			out.Metadata["image_error"] = err.Error()
		} else {
			out.CleanImageB64 = clean
		}
	}

	// Propagate safe metadata keys only (drop any PII keys)
	for k, v := range req.Metadata {
		if isSafeMetaKey(k) {
			out.Metadata[k] = v
		}
	}

	return out, nil
}

var allowedMetaKeys = map[string]bool{
	"content_type": true,
	"platform":     true,
	"language":     true,
	"timestamp":    true,
	"source_type":  true,
	// Public account signals for Axis 3 (source credibility) – not personal PII
	"username": true,
	"handle":   true,
	"bio":      true,
	"links":    true,
}

func isSafeMetaKey(k string) bool {
	return allowedMetaKeys[k]
}
