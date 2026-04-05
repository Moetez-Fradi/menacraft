import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../services/api_service.dart';
import '../models/verification_result.dart';
import '../main.dart' show AppColors;

// ─── Scan Record ───────────────────────────────────────────────────────────────
class _ScanRecord {
  final String source;
  final VerificationResult result;
  final DateTime timestamp;
  _ScanRecord({required this.source, required this.result, required this.timestamp});
}

// ─── Home Screen ───────────────────────────────────────────────────────────────
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with SingleTickerProviderStateMixin {
  bool _isLoading = false;
  final List<_ScanRecord> _history = [];

  late final AnimationController _pulseController;
  late final Animation<double> _pulseAnim;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2400),
    )..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _pickAndUploadFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['jpg', 'mp4', 'mp3', 'pdf'],
    );

    if (result == null || result.files.single.path == null) return;

    final file = result.files.single;
    setState(() => _isLoading = true);

    try {
      final verification = await ApiService.checkFile(file.path!, file.name);
      setState(() {
        _history.insert(
          0,
          _ScanRecord(source: file.name, result: verification, timestamp: DateTime.now()),
        );
      });
      if (mounted) {
        showModalBottomSheet(
          context: context,
          isScrollControlled: true,
          backgroundColor: Colors.transparent,
          builder: (_) => ResultBottomSheet(result: verification, source: file.name),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.only(bottom: 100),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildHeroHeader(),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _buildUploadZone(),
                    const SizedBox(height: 12),
                    _buildFormatChips(),
                    const SizedBox(height: 28),
                    if (_history.isNotEmpty) ...[
                      _buildRecentHeader(),
                      const SizedBox(height: 12),
                      _buildHistoryList(),
                    ] else
                      _buildTip(),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Hero Header ─────────────────────────────────────────────────────────────

  Widget _buildHeroHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: const Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Column(
        children: [
          // Top row: brand name + status pill
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: Color(0xFF5B3FD4),
                    ),
                  ),
                  const SizedBox(width: 6),
                  const Text(
                    'MENACRAFT',
                    style: TextStyle(
                      color: AppColors.text,
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.14,
                    ),
                  ),
                ],
              ),
              _buildStatusPill(),
            ],
          ),

          const SizedBox(height: 28),

          // Shield icon with animated glow
          AnimatedBuilder(
            animation: _pulseAnim,
            builder: (context, _) {
              return Stack(
                alignment: Alignment.center,
                children: [
                  // Outer glow ring
                  Container(
                    width: 88,
                    height: 88,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppColors.accent.withOpacity(0.08 * _pulseAnim.value),
                    ),
                  ),
                  // Inner glow
                  Container(
                    width: 68,
                    height: 68,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppColors.accent.withOpacity(0.14),
                      border: Border.all(
                        color: AppColors.accent.withOpacity(0.3 * _pulseAnim.value),
                        width: 1.5,
                      ),
                    ),
                    child: const Icon(
                      Icons.shield_rounded,
                      size: 34,
                      color: AppColors.accent2,
                    ),
                  ),
                ],
              );
            },
          ),

          const SizedBox(height: 18),

          const Text(
            'Digital Sieve',
            style: TextStyle(
              color: AppColors.text,
              fontSize: 24,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Detect fake media, AI-generated content\nand misinformation instantly.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppColors.text2,
              fontSize: 13.5,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusPill() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.safe.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.safe.withOpacity(0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedBuilder(
            animation: _pulseAnim,
            builder: (context, _) => Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.safe,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.safe.withOpacity(0.5 * _pulseAnim.value),
                    blurRadius: 5,
                    spreadRadius: 1,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 5),
          const Text(
            'Active',
            style: TextStyle(
              color: AppColors.safe,
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }

  // ─── Upload Zone ──────────────────────────────────────────────────────────────

  Widget _buildUploadZone() {
    return GestureDetector(
      onTap: _isLoading ? null : _pickAndUploadFile,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 24),
        decoration: BoxDecoration(
          color: _isLoading
              ? AppColors.accent.withOpacity(0.06)
              : AppColors.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: _isLoading
                ? AppColors.accent.withOpacity(0.5)
                : AppColors.accent.withOpacity(0.2),
            width: 1.5,
          ),
          boxShadow: [
            BoxShadow(
              color: AppColors.accent.withOpacity(_isLoading ? 0.12 : 0.06),
              blurRadius: 24,
              spreadRadius: 0,
            ),
          ],
        ),
        child: Column(
          children: [
            if (_isLoading) ...[
              SizedBox(
                width: 44,
                height: 44,
                child: CircularProgressIndicator(
                  strokeWidth: 3,
                  valueColor: const AlwaysStoppedAnimation<Color>(AppColors.accent),
                  backgroundColor: AppColors.accent.withOpacity(0.15),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Analysing…',
                style: TextStyle(
                  color: AppColors.accent2,
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ] else ...[
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: const LinearGradient(
                    colors: [Color(0xFF5B3FD4), AppColors.accent],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.accent.withOpacity(0.35),
                      blurRadius: 16,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.cloud_upload_rounded,
                  color: Colors.white,
                  size: 26,
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Select Media File',
                style: TextStyle(
                  color: AppColors.text,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.1,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Tap to browse your device',
                style: TextStyle(color: AppColors.muted, fontSize: 13),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // ─── Format Chips ─────────────────────────────────────────────────────────────

  Widget _buildFormatChips() {
    const formats = ['JPG', 'MP4', 'MP3', 'PDF'];
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: formats
          .expand((f) => [
                _FormatChip(label: f),
                if (f != formats.last)
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 6),
                    child: Text(
                      '·',
                      style: TextStyle(color: AppColors.muted, fontSize: 12),
                    ),
                  ),
              ])
          .toList(),
    );
  }

  // ─── Recent History ───────────────────────────────────────────────────────────

  Widget _buildRecentHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        const Text(
          'RECENT SCANS',
          style: TextStyle(
            color: AppColors.text2,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.1,
          ),
        ),
        GestureDetector(
          onTap: () => setState(() => _history.clear()),
          child: const Text(
            'Clear',
            style: TextStyle(
              color: AppColors.muted,
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.05,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildHistoryList() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: _history
            .take(8)
            .toList()
            .asMap()
            .entries
            .map((e) => _HistoryItem(
                  record: e.value,
                  isLast: e.key == (_history.length - 1).clamp(0, 7),
                ))
            .toList(),
      ),
    );
  }

  // ─── Tip ──────────────────────────────────────────────────────────────────────

  Widget _buildTip() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.accent.withOpacity(0.06),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.accent.withOpacity(0.12)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.bolt_rounded, color: AppColors.accent2, size: 18),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              'You can also share links directly from social media apps — tap Share, then choose Digital Sieve.',
              style: TextStyle(
                color: AppColors.text2,
                fontSize: 13,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Format Chip ───────────────────────────────────────────────────────────────
class _FormatChip extends StatelessWidget {
  final String label;
  const _FormatChip({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.border),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: AppColors.muted,
          fontSize: 10,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.08,
        ),
      ),
    );
  }
}

// ─── History Item ──────────────────────────────────────────────────────────────
class _HistoryItem extends StatelessWidget {
  final _ScanRecord record;
  final bool isLast;
  const _HistoryItem({required this.record, required this.isLast});

  Color get _verdictColor {
    switch (record.result.verdict.toLowerCase()) {
      case 'fake': return AppColors.danger;
      case 'ai':   return AppColors.warning;
      default:     return AppColors.safe;
    }
  }

  Color get _verdictBg {
    switch (record.result.verdict.toLowerCase()) {
      case 'fake': return AppColors.danger.withOpacity(0.12);
      case 'ai':   return AppColors.warning.withOpacity(0.12);
      default:     return AppColors.safe.withOpacity(0.12);
    }
  }

  String get _verdictLabel => record.result.verdict.toUpperCase();

  String _timeAgo() {
    final diff = DateTime.now().difference(record.timestamp);
    if (diff.inMinutes < 1)  return 'just now';
    if (diff.inHours < 1)    return '${diff.inMinutes}m ago';
    if (diff.inDays < 1)     return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  @override
  Widget build(BuildContext context) {
    final pct = (record.result.score * 100).round();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        border: isLast
            ? null
            : const Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  record.source,
                  style: const TextStyle(
                    color: AppColors.text,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: _verdictBg,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        _verdictLabel,
                        style: TextStyle(
                          color: _verdictColor,
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.06,
                        ),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      _timeAgo(),
                      style: const TextStyle(color: AppColors.muted, fontSize: 11),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
            decoration: BoxDecoration(
              color: _verdictBg,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              '$pct%',
              style: TextStyle(
                color: _verdictColor,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Result Bottom Sheet ───────────────────────────────────────────────────────
class ResultBottomSheet extends StatelessWidget {
  final VerificationResult result;
  final String source;
  const ResultBottomSheet({super.key, required this.result, required this.source});

  Color get _color {
    switch (result.verdict.toLowerCase()) {
      case 'fake': return AppColors.danger;
      case 'ai':   return AppColors.warning;
      default:     return AppColors.safe;
    }
  }

  Color get _colorDim {
    switch (result.verdict.toLowerCase()) {
      case 'fake': return AppColors.danger.withOpacity(0.12);
      case 'ai':   return AppColors.warning.withOpacity(0.12);
      default:     return AppColors.safe.withOpacity(0.12);
    }
  }

  IconData get _icon {
    switch (result.verdict.toLowerCase()) {
      case 'fake': return Icons.warning_amber_rounded;
      case 'ai':   return Icons.smart_toy_outlined;
      default:     return Icons.verified_rounded;
    }
  }

  String get _verdictLabel {
    switch (result.verdict.toLowerCase()) {
      case 'fake': return 'Fake Content';
      case 'ai':   return 'AI-Generated';
      default:     return 'Appears Real';
    }
  }

  @override
  Widget build(BuildContext context) {
    final pct = (result.score * 100).round();

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag handle
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),

          Padding(
            padding: EdgeInsets.fromLTRB(
              24, 20, 24, MediaQuery.of(context).viewInsets.bottom + 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header row
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Analysis Result',
                      style: TextStyle(
                        color: AppColors.text,
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        letterSpacing: -0.2,
                      ),
                    ),
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close_rounded, color: AppColors.muted),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),

                const SizedBox(height: 4),
                Text(
                  source,
                  style: const TextStyle(color: AppColors.muted, fontSize: 12),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),

                const SizedBox(height: 24),

                // Verdict + Score row
                Row(
                  children: [
                    // Verdict badge
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        color: _colorDim,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: _color.withOpacity(0.3)),
                      ),
                      child: Row(
                        children: [
                          Icon(_icon, color: _color, size: 20),
                          const SizedBox(width: 8),
                          Text(
                            _verdictLabel,
                            style: TextStyle(
                              color: _color,
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.2,
                            ),
                          ),
                        ],
                      ),
                    ),

                    const Spacer(),

                    // Score circle
                    SizedBox(
                      width: 64,
                      height: 64,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          CircularProgressIndicator(
                            value: result.score,
                            strokeWidth: 4,
                            backgroundColor: _color.withOpacity(0.12),
                            valueColor: AlwaysStoppedAnimation<Color>(_color),
                          ),
                          Text(
                            '$pct%',
                            style: TextStyle(
                              color: _color,
                              fontSize: 14,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 24),

                // Confidence bar
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'CONFIDENCE',
                          style: TextStyle(
                            color: AppColors.text2,
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.1,
                          ),
                        ),
                        Text(
                          '${pct}%',
                          style: TextStyle(
                            color: _color,
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: result.score,
                        minHeight: 5,
                        backgroundColor: _color.withOpacity(0.1),
                        valueColor: AlwaysStoppedAnimation<Color>(_color),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 24),

                // Reasoning
                const Text(
                  'ANALYSIS',
                  style: TextStyle(
                    color: AppColors.text2,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.1,
                  ),
                ),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.surface2,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: Text(
                    result.reasoning,
                    style: const TextStyle(
                      color: AppColors.text2,
                      fontSize: 13.5,
                      height: 1.6,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
