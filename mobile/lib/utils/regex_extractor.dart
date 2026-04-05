class RegexExtractor {
  static String? extractUrl(String input) {
    // Stage 1 constraint: Regex to strip marketing text leaving the raw https:// link
    final RegExp urlRegex = RegExp(
      r'(https?|ftp|file)://[-a-zA-Z0-9+&@#/%?=~_|!:,.;]*[-a-zA-Z0-9+&@#/%=~_|]',
      caseSensitive: false,
    );

    final match = urlRegex.firstMatch(input);
    if (match != null) {
      return match.group(0);
    }
    return null;
  }
}
