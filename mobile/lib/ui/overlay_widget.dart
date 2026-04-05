import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_overlay_window/flutter_overlay_window.dart';
import '../services/api_service.dart';
import '../utils/regex_extractor.dart';

class OverlayWidget extends StatefulWidget {
  const OverlayWidget({Key? key}) : super(key: key);

  @override
  State<OverlayWidget> createState() => _OverlayWidgetState();
}

class _OverlayWidgetState extends State<OverlayWidget> {
  bool _isExpanded = false;
  bool _isProcessing = false;
  String _verdict = '';

  Future<void> _handlePasteAndVerify() async {
    setState(() => _isProcessing = true);
    
    // 1. Read Clipboard
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final rawText = data?.text ?? '';
    
    // 2. Extract URL via Regex
    final extractedUrl = RegexExtractor.extractUrl(rawText);

    if (extractedUrl == null) {
      setState(() {
        _verdict = 'No valid URL found on clipboard.';
        _isProcessing = false;
      });
      return;
    }

    // 3. Sent to Service
    final result = await ApiService.checkUrl(extractedUrl);

    setState(() {
      _verdict = 'Verdict: ${result.verdict}\nScore: ${result.score}\nReason: ${result.reasoning}';
      _isProcessing = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: GestureDetector(
        onTap: () {
          setState(() {
            _isExpanded = !_isExpanded;
            // Optionally, resize the overlay bubble depending on state
            if (_isExpanded) {
              FlutterOverlayWindow.resizeOverlay(300, 250, true);
            } else {
              FlutterOverlayWindow.resizeOverlay(80, 80, false);
              _verdict = ''; // Clear prior results on shrink
            }
          });
        },
        child: Container(
          decoration: BoxDecoration(
            color: _isExpanded ? Colors.grey[900]?.withOpacity(0.95) : Colors.blueAccent,
            borderRadius: BorderRadius.circular(_isExpanded ? 16 : 40),
            boxShadow: const [BoxShadow(color: Colors.black45, blurRadius: 10)],
          ),
          padding: const EdgeInsets.all(12),
          child: _isExpanded 
              ? _buildExpandedUI() 
              : const Center(child: Icon(Icons.security, color: Colors.white, size: 36)),
        ),
      ),
    );
  }

  Widget _buildExpandedUI() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text(
          "Trust-Guard", 
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 18)
        ),
        const SizedBox(height: 16),
        if (_isProcessing)
          const CircularProgressIndicator(color: Colors.blueAccent)
        else ...[
          ElevatedButton.icon(
            onPressed: () {
              _handlePasteAndVerify();
            }, 
            icon: const Icon(Icons.paste), 
            label: const Text('Paste & Verify')
          ),
          if (_verdict.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 12.0),
              child: Text(
                _verdict,
                style: const TextStyle(color: Colors.white70, fontSize: 12),
                textAlign: TextAlign.center,
              ),
            ),
        ]
      ],
    );
  }
}
