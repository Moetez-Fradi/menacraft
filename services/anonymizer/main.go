package main

import (
	"log"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
)

func main() {
	app := fiber.New(fiber.Config{
		AppName:       "MENACRAFT Anonymizer",
		StrictRouting: true,
	})

	app.Use(logger.New())
	app.Use(recover.New())

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok"})
	})

	app.Post("/anonymize", handleAnonymize)

	log.Fatal(app.Listen(":8081"))
}

func handleAnonymize(c *fiber.Ctx) error {
	var req AnonymizeRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "invalid JSON: " + err.Error()})
	}

	if req.ContentType == "" {
		req.ContentType = "text"
	}

	payload, err := Process(req)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}

	return c.JSON(payload)
}
