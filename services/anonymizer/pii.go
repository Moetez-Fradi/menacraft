package main

import (
	"regexp"
	"strings"
)

var (
	emailRe = regexp.MustCompile(`[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}`)
	phoneRe = regexp.MustCompile(`(\+?[\d][\d\s\-().]{7,}\d)`)
	// Name heuristic: capitalized word pairs not at sentence start
	nameRe = regexp.MustCompile(`\b([A-Z][a-z]{2,})\s([A-Z][a-z]{2,})\b`)
)

// AnonymizeText replaces PII in text with labeled placeholders.
func AnonymizeText(text string) string {
	emailCount := 0
	text = emailRe.ReplaceAllStringFunc(text, func(_ string) string {
		emailCount++
		return placeholder("EMAIL", emailCount)
	})

	phoneCount := 0
	text = phoneRe.ReplaceAllStringFunc(text, func(_ string) string {
		phoneCount++
		return placeholder("PHONE", phoneCount)
	})

	nameCount := 0
	text = nameRe.ReplaceAllStringFunc(text, func(_ string) string {
		nameCount++
		return placeholder("NAME", nameCount)
	})

	return strings.TrimSpace(text)
}

func placeholder(kind string, n int) string {
	// e.g. [EMAIL_1]
	return "[" + kind + "_" + itoa(n) + "]"
}

func itoa(n int) string {
	const digits = "0123456789"
	if n == 0 {
		return "0"
	}
	buf := make([]byte, 0, 10)
	for n > 0 {
		buf = append([]byte{digits[n%10]}, buf...)
		n /= 10
	}
	return string(buf)
}
