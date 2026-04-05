import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_overlay_window/flutter_overlay_window.dart';
import '../services/api_service.dart';
import '../utils/regex_extractor.dart';
import '../models/verification_result.dart';
import '../main.dart' show AppColors;

class OverlayWidget extends StatefulWidget {
  const OverlayWidget({super.key});

  @override
  State<OverlayWidget> createState() => _OverlayWidgetState();
}

class _OverlayWidgetState extends State<OverlayWidget>
    with SingleTickerProviderStateMixin {
  bool _isExpanded = false;
  bool _isProcessing = false;
  VerificationResult? _result;
  String? _errorMsg;

  late final AnimationController _expandController;
  late final Animation<double> _expandAnim;

  @override
  void initState() {
    super.initState();
    _expandController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 260),
    );
    _expandAnim = CurvedAnimation(
      parent: _expandController,
      curve: Curves.easeOutCubic,
    );
  }

  @override
  void dispose() {
    _expandController.dispose();
    super.dispose();
  }

  void _toggle() {
    setState(() {
      _isExpanded = !_isExpanded;
      if (_isExpanded) {
        _expandController.forward();
        FlutterOverlayWindow.resizeOverlay(300, 260, true);
      } else {
        _expandController.reverse();
        _result = null;
        _errorMsg = null;
        FlutterOverlayWindow.resizeOverlay(70, 70, false);
      }
    });
  }

  Future<void> _pasteAndVerify() async {
    setState(() {
      _isProcessing = true;
      _result = null;
      _errorMsg = null;
    });

    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final rawText = data?.text ?? '';
    final url = RegexExtractor.extractUrl(rawText);

    if (url == null) {
      setState(() {
        _errorMsg = 'No valid URL on clipboard.';
        _isProcessing = false;
      });
      return;
    }

    try {
      final result = await ApiService.checkUrl(url);
      setState(() {
        _result = result;
        _isProcessing = false;
      });
    } catch (e) {
      setState(() {
        _errorMsg = 'Verification failed.';
        _isProcessing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: GestureDetector(
        onTap: _isExpanded ? null : _toggle,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 260),
          curve: Curves.easeOutCubic,
          width: _isExpanded ? 300 : 70,
          height: _isExpanded ? 260 : 70,
          decoration: BoxDecoration(
            color: _isExpanded ? AppColors.surface : Colors.transparent,
            borderRadius: BorderRadius.circular(_isExpanded ? 20 : 35),
            border: _isExpanded
                ? Border.all(color: AppColors.border)
                : null,
            boxShadow: [
              BoxShadow(
                color: AppColors.accent.withOpacity(_isExpanded ? 0.12 : 0.35),
                blurRadius: _isExpanded ? 24 : 16,
                spreadRadius: _isExpanded ? 0 : -2,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: _isExpanded ? _buildExpandedUI() : _buildCollapsedBubble(),
        ),
      ),
    );
  }

  // ─── Collapsed Bubble ─────────────────────────────────────────────────────────

  Widget _buildCollapsedBubble() {
    return Container(
      width: 70,
      height: 70,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          colors: [Color(0xFF5B3FD4), AppColors.accent],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: const Icon(
        Icons.shield_rounded,
        color: Colors.white,
        size: 30,
      ),
    );
  }

  // ─── Expanded Panel ───────────────────────────────────────────────────────────

  Widget _buildExpandedUI() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppColors.accent.withOpacity(0.15),
                    ),
                    child: const Icon(
                      Icons.shield_rounded,
                      color: AppColors.accent2,
                      size: 15,
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Text(
                    'Digital Sieve',
                    style: TextStyle(
                      color: AppColors.text,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
              GestureDetector(
                onTap: _toggle,
                child: Container(
                  width: 26,
                  height: 26,
                  decoration: BoxDecoration(
                    color: AppColors.surface2,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.close_rounded,
                    color: AppColors.muted,
                    size: 15,
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 14),
          Container(height: 1, color: AppColors.border),
          const SizedBox(height: 14),

          // Content area
          Expanded(
            child: _isProcessing
                ? _buildProcessingState()
                : _result != null
                    ? _buildResultState(_result!)
                    : _errorMsg != null
                        ? _buildErrorState(_errorMsg!)
                        : _buildIdleState(),
          ),
        ],
      ),
    );
  }

  Widget _buildIdleState() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Text(
          'Copy a link, then tap below to verify it instantly.',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: AppColors.text2,
            fontSize: 12,
            height: 1.5,
          ),
        ),
        const SizedBox(height: 16),
        _PasteButton(onTap: _pasteAndVerify),
      ],
    );
  }

  Widget _buildProcessingState() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        SizedBox(
          width: 36,
          height: 36,
          child: CircularProgressIndicator(
            strokeWidth: 3,
            valueColor: const AlwaysStoppedAnimation<Color>(AppColors.accent),
            backgroundColor: AppColors.accent.withOpacity(0.15),
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          'Verifying…',
          style: TextStyle(
            color: AppColors.text2,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildResultState(VerificationResult result) {
    final verdict = result.verdict.toLowerCase();
    final color = verdict == 'fake'
        ? AppColors.danger
        : verdict == 'ai'
            ? AppColors.warning
            : AppColors.safe;
    final colorDim = color.withOpacity(0.12);
    final label = verdict == 'fake'
        ? 'Fake'
        : verdict == 'ai'
            ? 'AI-Generated'
            : 'Appears Real';
    final icon = verdict == 'fake'
        ? Icons.warning_amber_rounded
        : verdict == 'ai'
            ? Icons.smart_toy_outlined
            : Icons.verified_rounded;
    final pct = (result.score * 100).round();

    return Column(
      children: [
        // Verdict row
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: colorDim,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withOpacity(0.25)),
          ),
          child: Row(
            children: [
              Icon(icon, color: color, size: 16),
              const SizedBox(width: 7),
              Text(
                label,
                style: TextStyle(
                  color: color,
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const Spacer(),
              Text(
                '$pct%',
                style: TextStyle(
                  color: color,
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 10),

        // Confidence bar
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: result.score,
            minHeight: 4,
            backgroundColor: color.withOpacity(0.1),
            valueColor: AlwaysStoppedAnimation<Color>(color),
          ),
        ),

        const SizedBox(height: 12),

        // Reasoning (truncated)
        Text(
          result.reasoning,
          style: const TextStyle(
            color: AppColors.text2,
            fontSize: 11,
            height: 1.5,
          ),
          maxLines: 3,
          overflow: TextOverflow.ellipsis,
        ),

        const Spacer(),
        _PasteButton(onTap: _pasteAndVerify, label: 'Verify Another'),
      ],
    );
  }

  Widget _buildErrorState(String msg) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 28),
        const SizedBox(height: 10),
        Text(
          msg,
          textAlign: TextAlign.center,
          style: const TextStyle(color: AppColors.text2, fontSize: 12),
        ),
        const SizedBox(height: 14),
        _PasteButton(onTap: _pasteAndVerify),
      ],
    );
  }
}

// ─── Paste Button ──────────────────────────────────────────────────────────────
class _PasteButton extends StatelessWidget {
  final VoidCallback onTap;
  final String label;
  const _PasteButton({required this.onTap, this.label = 'Paste & Verify'});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF5B3FD4), AppColors.accent],
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
          ),
          borderRadius: BorderRadius.circular(10),
          boxShadow: [
            BoxShadow(
              color: AppColors.accent.withOpacity(0.3),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.content_paste_rounded, color: Colors.white, size: 14),
            const SizedBox(width: 7),
            Text(
              label,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
