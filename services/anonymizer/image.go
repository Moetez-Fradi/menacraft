package main

import (
	"bytes"
	"encoding/base64"
	"errors"
	"image"
	"image/color"
	"image/draw"
	_ "image/gif"
	"image/jpeg"
	_ "image/png"
)

// StripAndAnonymizeImage decodes a base64 image, strips EXIF by re-encoding,
// blurs the top and bottom 10% strips (common overlay/watermark zones), and
// returns a fresh base64 JPEG with no original metadata.
func StripAndAnonymizeImage(b64 string) (string, error) {
	raw, err := base64.StdEncoding.DecodeString(b64)
	if err != nil {
		// Try URL-safe variant
		raw, err = base64.URLEncoding.DecodeString(b64)
		if err != nil {
			return "", errors.New("invalid base64 image")
		}
	}

	img, _, err := image.Decode(bytes.NewReader(raw))
	if err != nil {
		return "", err
	}

	bounds := img.Bounds()
	w, h := bounds.Max.X, bounds.Max.Y

	// Convert to RGBA so we can draw on it
	rgba := image.NewRGBA(bounds)
	draw.Draw(rgba, bounds, img, bounds.Min, draw.Src)

	// Blur top 10% and bottom 10% (text overlay / caption regions)
	blurBand(rgba, 0, h/10, w)
	blurBand(rgba, h-h/10, h, w)

	// Re-encode as JPEG — this naturally strips all EXIF metadata
	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, rgba, &jpeg.Options{Quality: 85}); err != nil {
		return "", err
	}

	return base64.StdEncoding.EncodeToString(buf.Bytes()), nil
}

// blurBand applies a box-blur over a horizontal strip of the image.
func blurBand(img *image.RGBA, yStart, yEnd, width int) {
	const radius = 8
	bounds := img.Bounds()
	if yEnd > bounds.Max.Y {
		yEnd = bounds.Max.Y
	}
	// Simple average over radius×radius blocks
	for y := yStart; y < yEnd; y++ {
		for x := 0; x < width; x++ {
			var r, g, b, a, n uint32
			for dy := -radius; dy <= radius; dy++ {
				for dx := -radius; dx <= radius; dx++ {
					nx, ny := x+dx, y+dy
					if nx < 0 || ny < 0 || nx >= width || ny >= bounds.Max.Y {
						continue
					}
					cr, cg, cb, ca := img.At(nx, ny).RGBA()
					r += cr >> 8
					g += cg >> 8
					b += cb >> 8
					a += ca >> 8
					n++
				}
			}
			if n > 0 {
				img.SetRGBA(x, y, color.RGBA{
					R: uint8(r / n),
					G: uint8(g / n),
					B: uint8(b / n),
					A: uint8(a / n),
				})
			}
		}
	}
}
