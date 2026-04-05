class VerificationResult {
  final String verdict;
  final double score;
  final String reasoning;

  VerificationResult({
    required this.verdict,
    required this.score,
    required this.reasoning,
  });

  factory VerificationResult.fromJson(Map<String, dynamic> json) {
    // If the orchestrator returns a raw response, we mock parsing the standard fields
    // according to the 12-hour hackathon MVP spec:
    return VerificationResult(
      verdict: json['verdict'] ?? 'Unknown',
      score: (json['score'] ?? 0.0).toDouble(),
      reasoning: json['reasoning'] ?? 'No reasoning provided.',
    );
  }
}
