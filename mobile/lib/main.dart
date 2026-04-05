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

// ─── Brand Colors ──────────────────────────────────────────────────────────────
class AppColors {
  static const bg         = Color(0xFF09090E);
  static const surface    = Color(0xFF111118);
  static const surface2   = Color(0xFF18181F);
  static const surface3   = Color(0xFF1F1F28);
  static const border     = Color(0x0FFFFFFF);
  static const text       = Color(0xFFF0F0F6);
  static const text2      = Color(0xFF9898B0);
  static const muted      = Color(0xFF4C4C62);
  static const safe       = Color(0xFF0FCF82);
  static const warning    = Color(0xFFF5A623);
  static const danger     = Color(0xFFF04559);
  static const accent     = Color(0xFF7C5CFC);
  static const accent2    = Color(0xFFA78BFA);
}

// ─── Overlay Entry Point ───────────────────────────────────────────────────────
@pragma("vm:entry-point")
void overlayMain() {
  runApp(
    MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(),
      home: const OverlayWidget(),
    ),
  );
}

ThemeData _buildTheme() {
  return ThemeData(
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AppColors.bg,
    colorScheme: const ColorScheme.dark(
      primary: AppColors.accent,
      primaryContainer: Color(0xFF1F1A35),
      secondary: AppColors.accent2,
      surface: AppColors.surface,
      error: AppColors.danger,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.surface,
      elevation: 0,
      centerTitle: true,
      titleTextStyle: TextStyle(
        color: AppColors.text,
        fontSize: 16,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.3,
      ),
      iconTheme: IconThemeData(color: AppColors.text2),
    ),
    cardTheme: CardThemeData(
      color: AppColors.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppColors.border),
      ),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: AppColors.surface,
      modalBackgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: AppColors.surface2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      titleTextStyle: const TextStyle(
        color: AppColors.text,
        fontSize: 17,
        fontWeight: FontWeight.w700,
      ),
      contentTextStyle: const TextStyle(color: AppColors.text2, fontSize: 14),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: AppColors.surface2,
      contentTextStyle: const TextStyle(color: AppColors.text),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      behavior: SnackBarBehavior.floating,
    ),
    textTheme: const TextTheme(
      displayLarge:   TextStyle(color: AppColors.text,  fontWeight: FontWeight.w800),
      headlineLarge:  TextStyle(color: AppColors.text,  fontWeight: FontWeight.w800),
      headlineMedium: TextStyle(color: AppColors.text,  fontWeight: FontWeight.w700),
      headlineSmall:  TextStyle(color: AppColors.text,  fontWeight: FontWeight.w700),
      titleLarge:     TextStyle(color: AppColors.text,  fontWeight: FontWeight.w600),
      titleMedium:    TextStyle(color: AppColors.text,  fontWeight: FontWeight.w500),
      titleSmall:     TextStyle(color: AppColors.text2, fontWeight: FontWeight.w500),
      bodyLarge:      TextStyle(color: AppColors.text2),
      bodyMedium:     TextStyle(color: AppColors.text2),
      bodySmall:      TextStyle(color: AppColors.muted),
      labelLarge:     TextStyle(color: AppColors.text,  fontWeight: FontWeight.w600),
    ),
    useMaterial3: true,
  );
}

// ─── App ───────────────────────────────────────────────────────────────────────
void main() {
  runApp(const TrustGuardApp());
}

class TrustGuardApp extends StatelessWidget {
  const TrustGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MENACRAFT',
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(),
      home: const AppScaffold(),
    );
  }
}

// ─── App Scaffold ──────────────────────────────────────────────────────────────
class AppScaffold extends StatefulWidget {
  const AppScaffold({super.key});

  @override
  State<AppScaffold> createState() => _AppScaffoldState();
}

class _AppScaffoldState extends State<AppScaffold> {
  late StreamSubscription _intentDataStreamSubscription;

  @override
  void initState() {
    super.initState();
    _requestPermissions();
    _initSharingIntent();
  }

  Future<void> _requestPermissions() async {
    await [
      Permission.systemAlertWindow,
      Permission.storage,
      Permission.videos,
      Permission.photos,
      Permission.audio,
    ].request();
  }

  void _initSharingIntent() {
    _intentDataStreamSubscription =
        ReceiveSharingIntent.instance.getMediaStream().listen(
      (List<SharedMediaFile> value) {
        if (value.isNotEmpty) {
          final first = value.first;
          if (first.type == SharedMediaType.text ||
              first.type == SharedMediaType.url) {
            _handleSharedText(first.path);
          }
        }
      },
      onError: (err) => debugPrint('getIntentDataStream error: $err'),
    );

    ReceiveSharingIntent.instance
        .getInitialMedia()
        .then((List<SharedMediaFile> value) {
      if (value.isNotEmpty) {
        final first = value.first;
        if (first.type == SharedMediaType.text ||
            first.type == SharedMediaType.url) {
          _handleSharedText(first.path);
        }
      }
    });
  }

  void _handleSharedText(String text) {
    final extractedUrl = RegexExtractor.extractUrl(text);
    if (extractedUrl != null) {
      _showVerificationProcess(extractedUrl);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No valid link found in shared content.')),
      );
    }
  }

  void _showVerificationProcess(String url) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      barrierColor: Colors.black.withOpacity(0.7),
      builder: (context) => _VerifyingDialog(url: url),
    );

    try {
      final result = await ApiService.checkUrl(url);
      if (mounted) Navigator.pop(context);
      if (mounted) {
        showModalBottomSheet(
          context: context,
          isScrollControlled: true,
          backgroundColor: Colors.transparent,
          builder: (_) => ResultBottomSheet(result: result, source: url),
        );
      }
    } catch (e) {
      if (mounted) Navigator.pop(context);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Verification failed: $e')),
        );
      }
    }
  }

  @override
  void dispose() {
    _intentDataStreamSubscription.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: _OverlayFab(),
      body: const HomeScreen(),
    );
  }
}

// ─── Overlay FAB ───────────────────────────────────────────────────────────────
class _OverlayFab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          colors: [Color(0xFF5B3FD4), AppColors.accent, AppColors.accent2],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.accent.withOpacity(0.4),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: FloatingActionButton.extended(
        onPressed: () async {
          if (await FlutterOverlayWindow.isPermissionGranted()) {
            await FlutterOverlayWindow.showOverlay(
              enableDrag: true,
              flag: OverlayFlag.focusPointer,
              alignment: OverlayAlignment.centerLeft,
              visibility: NotificationVisibility.visibilityPublic,
              positionGravity: PositionGravity.left,
              height: 70,
              width: 70,
            );
          } else {
            await FlutterOverlayWindow.requestPermission();
          }
        },
        backgroundColor: Colors.transparent,
        elevation: 0,
        label: const Text(
          'Shield',
          style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.5,
          ),
        ),
        icon: const Icon(Icons.security_rounded, color: Colors.white),
      ),
    );
  }
}

// ─── Verifying Dialog ──────────────────────────────────────────────────────────
class _VerifyingDialog extends StatelessWidget {
  final String url;
  const _VerifyingDialog({required this.url});

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 48,
              height: 48,
              child: CircularProgressIndicator(
                strokeWidth: 3,
                valueColor: const AlwaysStoppedAnimation<Color>(AppColors.accent),
                backgroundColor: AppColors.accent.withOpacity(0.15),
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Verifying Link…',
              style: TextStyle(
                color: AppColors.text,
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              Uri.tryParse(url)?.host ?? url,
              style: const TextStyle(
                color: AppColors.muted,
                fontSize: 12,
              ),
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
