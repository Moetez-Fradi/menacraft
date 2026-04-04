package main

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
)

var anonymizerURL = envOr("ANONYMIZER_URL", "http://anonymizer:8081")

func main() {
	app := fiber.New(fiber.Config{
		AppName:       "MENACRAFT Orchestrator",
		StrictRouting: true,
	})

	app.Use(logger.New())
	app.Use(recover.New())

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok"})
	})

	// Main analysis endpoint
	app.Post("/analyze", handleAnalyze)

	log.Fatal(app.Listen(":8080"))
}

// incomingRequest captures just the text field from the client payload.
type incomingRequest struct {
	Text string `json:"text"`
}

// handleAnalyze: anonymize → fan-out → aggregate → respond
func handleAnalyze(c *fiber.Ctx) error {
	rawBody := c.Body()

	// Extract original text before anonymization (for truth-retrieval search)
	var incoming incomingRequest
	_ = json.Unmarshal(rawBody, &incoming)

	// 1. Forward raw request to anonymizer
	anonResp, err := anonymize(rawBody)
	if err != nil {
		return c.Status(502).JSON(fiber.Map{"error": "anonymizer: " + err.Error()})
	}

	// 2. Build analysis request from clean payload
	req := AnalyzeRequest{
		SessionID:     anonResp.SessionID,
		CleanText:     anonResp.CleanText,
		RawText:       incoming.Text, // kept for truth search only, never sent to ML models
		CleanImageB64: anonResp.CleanImageB64,
		ContentType:   anonResp.ContentType,
		Metadata:      anonResp.Metadata,
	}

	// 3. Run the engine (parallel axes)
	result := Run(req)

	return c.JSON(result)
}

// anonymize proxies the raw body to the anonymizer service.
func anonymize(body []byte) (*AnonimizerResponse, error) {
	resp, err := http.Post(anonymizerURL+"/anonymize", "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	var out AnonimizerResponse
	return &out, json.Unmarshal(raw, &out)
}

// AnonimizerResponse mirrors the anonymizer output contract.
type AnonimizerResponse struct {
	SessionID     string                 `json:"session_id"`
	CleanText     string                 `json:"clean_text"`
	CleanImageB64 string                 `json:"clean_image_base64,omitempty"`
	ContentType   string                 `json:"content_type"`
	Metadata      map[string]interface{} `json:"metadata"`
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
