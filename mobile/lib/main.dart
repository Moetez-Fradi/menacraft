import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_overlay_window/flutter_overlay_window.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import 'package:permission_handler/permission_handler.dart';

import 'ui/home_screen.dart';
import 'ui/overlay_widget.dart';
import 'services/api_service.dart';
import 'utils/regex_extractor.dart';
import 'models/verification_result.dart';

// Overlay Entry Point (Module B)
@pragma("vm:entry-point")
void overlayMain() {
  runApp(
    MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(),
      home: const OverlayWidget(),
    ),
  );
}

void main() {
  runApp(const TrustGuardApp());
}

class TrustGuardApp extends StatelessWidget {
  const TrustGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Trust-Guard',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueAccent),
        useMaterial3: true,
      ),
      home: const AppScaffold(),
    );
  }
}

class AppScaffold extends StatefulWidget {
  const AppScaffold({super.key});

  @override
  State<AppScaffold> createState() => _AppScaffoldState();
}

class _AppScaffoldState extends State<AppScaffold> {
  late StreamSubscription _intentDataStreamSubscription;
  String? _sharedText;

  @override
  void initState() {
    super.initState();
    _requestPermissions();
    _initSharingIntent();
    _initOverlay();
  }

  Future<void> _requestPermissions() async {
    // Stage 4 constraints: Permissions
    await [
      Permission.systemAlertWindow,
      Permission.storage, // For file picking fallback
      Permission.videos,
      Permission.photos,
      Permission.audio,
    ].request();
  }

  void _initOverlay() async {
    // Check if overlay is already active, if not, we can show it later
    // For MVP, we auto-start the bubble if permission is granted
    if (await FlutterOverlayWindow.isPermissionGranted()) {
      debugPrint("Overlay permission granted, starting bubble...");
      // In a real app, you might want to wait for user interaction or show a toggle
      // but for Hackathon MVP, let's just make it accessible.
    }
  }

  void _initSharingIntent() {
    // Stage 1: Intercepting "Share to" actions
    _intentDataStreamSubscription = ReceiveSharingIntent.instance.getMediaStream().listen((List<SharedMediaFile> value) {
      if (value.isNotEmpty) {
        final first = value.first;
        if (first.type == SharedMediaType.text || first.type == SharedMediaType.url) {
          debugPrint("Received sharing intent: ${first.path}");
          _handleSharedText(first.path);
        }
      }
    }, onError: (err) {
      debugPrint("getIntentDataStream error: $err");
    });

    // Handle intent when app is totally closed
    ReceiveSharingIntent.instance.getInitialMedia().then((List<SharedMediaFile> value) {
      if (value.isNotEmpty) {
        final first = value.first;
        if (first.type == SharedMediaType.text || first.type == SharedMediaType.url) {
          debugPrint("Initial sharing intent: ${first.path}");
          _handleSharedText(first.path);
        }
      }
    });
  }

  void _handleSharedText(String text) async {
    final extractedUrl = RegexExtractor.extractUrl(text);
    if (extractedUrl != null) {
      // Show notification or just navigate to process
      _showVerificationProcess(extractedUrl);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No valid link found in shared content.')),
      );
    }
  }

  void _showVerificationProcess(String url) async {
    // High-speed verification UI
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('Verifying Shared Link...'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(url, style: const TextStyle(fontSize: 12, color: Colors.grey)),
          ],
        ),
      ),
    );

    try {
      final result = await ApiService.checkUrl(url);
      Navigator.pop(context); // Close dialog

      // Show result using the same bottom sheet style as HomeScreen or similar
      _showResultBottomSheet(result);
    } catch (e) {
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Verification failed: $e')),
      );
    }
  }

  void _showResultBottomSheet(VerificationResult result) {
    // Reuse logic or common UI
    final homeState = context.findAncestorStateOfType<State<HomeScreen>>();
    // Since we are in Scaffolf, let's just show it here.
    // In a real app we'd have a global key or state management.
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => _ResultSheetContent(result: result),
    );
  }

  @override
  void dispose() {
    _intentDataStreamSubscription.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          if (await FlutterOverlayWindow.isPermissionGranted()) {
            await FlutterOverlayWindow.showOverlay(
              enableDrag: true,
              flag: OverlayFlag.focusPointer,
              alignment: OverlayAlignment.centerLeft,
              visibility: NotificationVisibility.visibilityPublic,
              positionGravity: PositionGravity.left,
              height: 80,
              width: 80,
            );
          } else {
            await FlutterOverlayWindow.requestPermission();
          }
        },
        label: const Text('Toggle Shield'),
        icon: const Icon(Icons.security),
      ),
      body: const HomeScreen(),
    );
  }
}

class _ResultSheetContent extends StatelessWidget {
  final VerificationResult result;
  const _ResultSheetContent({required this.result});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Verdict: ${result.verdict}', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text('Score: ${result.score.toStringAsFixed(2)}'),
          const SizedBox(height: 16),
          Text(result.reasoning),
          const SizedBox(height: 24),
          ElevatedButton(onPressed: () => Navigator.pop(context), child: const Text('Close')),
        ],
      ),
    );
  }
}
