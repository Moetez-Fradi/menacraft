import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/verification_result.dart';

class ApiService {
  // Pointing to the local orchestrator node for the Android emulator. 
  // 10.0.2.2 resolves to localhost on the host machine.
  static const String baseUrl = 'http://10.108.237.136:8080';

  static Future<VerificationResult> checkUrl(String url) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/analyze'),
        headers: {'Content-Type': 'application/json'},
        // The orchestrator specifically takes {"text": "..."} according to main.go
        // But we inject the URL as text. We also inject metadata just in case.
        body: jsonEncode({
          'text': url,
          'source_app': 'Trust-Guard Mobile', // Extraneous for MVP but specifies intent
        }),
      );

      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        return VerificationResult.fromJson(decoded);
      } else {
        throw Exception('Server error: ${response.statusCode}');
      }
    } catch (e) {
      // Mocked fallback for Hackathon if server is unreachable
      return VerificationResult(
        verdict: 'Error',
        score: 0.0,
        reasoning: 'API Connection failed: $e',
      );
    }
  }

  static Future<VerificationResult> checkFile(String filePath, String fileName) async {
    try {
      var request = http.MultipartRequest('POST', Uri.parse('$baseUrl/check-file'));
      
      // Attach the file stream
      request.files.add(await http.MultipartFile.fromPath(
        'file',
        filePath,
        filename: fileName,
      ));

      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        return VerificationResult.fromJson(decoded);
      } else {
        throw Exception('File Upload Failed: ${response.statusCode}');
      }
    } catch (e) {
      return VerificationResult(
        verdict: 'Error',
        score: 0.0,
        reasoning: 'Multipart Upload failed: $e',
      );
    }
  }
}
