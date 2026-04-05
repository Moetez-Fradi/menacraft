import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../services/api_service.dart';
import '../models/verification_result.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _isLoading = false;
  VerificationResult? _lastResult;

  Future<void> _pickAndUploadFile() async {
    FilePickerResult? result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['jpg', 'mp4', 'mp3', 'pdf'],
    );

    if (result != null && result.files.single.path != null) {
      setState(() {
        _isLoading = true;
        _lastResult = null;
      });

      try {
        final verification = await ApiService.checkFile(
          result.files.single.path!,
          result.files.single.name,
        );
        setState(() => _lastResult = verification);
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e')),
        );
      } finally {
        setState(() => _isLoading = false);
      }
    }
  }

  void _showResultSheet(VerificationResult result) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Verification Result',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _ResultBadge(verdict: result.verdict),
            const SizedBox(height: 16),
            Text(
              'Confidence Score: ${(result.score * 100).toStringAsFixed(1)}%',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: result.score,
              backgroundColor: Colors.grey[200],
              color: _getVerdictColor(result.verdict),
            ),
            const SizedBox(height: 24),
            Text(
              'Reasoning',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.grey[600],
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              result.reasoning,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Color _getVerdictColor(String verdict) {
    switch (verdict.toLowerCase()) {
      case 'real':
        return Colors.green;
      case 'fake':
        return Colors.red;
      case 'ai':
        return Colors.orange;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_lastResult != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _showResultSheet(_lastResult!);
        setState(() => _lastResult = null);
      });
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Trust-Guard Dashboard'),
        centerTitle: true,
      ),
      body: Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildHeader(),
            const Spacer(),
            _buildUploadCard(),
            const Spacer(),
            _buildInstructions(),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      children: [
        const Icon(Icons.shield_outlined, size: 80, color: Colors.blueAccent),
        const SizedBox(height: 16),
        Text(
          'Media Verification',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 8),
        Text(
          'Upload images, videos, or audio for AI analysis',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.grey[600],
              ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }

  Widget _buildUploadCard() {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: InkWell(
        onTap: _isLoading ? null : _pickAndUploadFile,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 48, horizontal: 24),
          child: Column(
            children: [
              if (_isLoading)
                const CircularProgressIndicator()
              else ...[
                const Icon(Icons.cloud_upload_outlined, size: 48, color: Colors.blue),
                const SizedBox(height: 16),
                const Text(
                  'Select Media File',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                Text(
                  'JPG, MP4, MP3, PDF up to 50MB',
                  style: TextStyle(color: Colors.grey[500], fontSize: 13),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildInstructions() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.blue.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blue.withOpacity(0.1)),
      ),
      child: Row(
        children: [
          const Icon(Icons.lightbulb_outline, color: Colors.blue),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'Pro tip: You can also share links from social media directly to this app for quick analysis.',
              style: TextStyle(color: Colors.blue[800], fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}

class _ResultBadge extends StatelessWidget {
  final String verdict;

  const _ResultBadge({required this.verdict});

  @override
  Widget build(BuildContext context) {
    Color color;
    IconData icon;
    switch (verdict.toLowerCase()) {
      case 'real':
        color = Colors.green;
        icon = Icons.check_circle_outline;
        break;
      case 'fake':
        color = Colors.red;
        icon = Icons.error_outline;
        break;
      case 'ai':
        color = Colors.orange;
        icon = Icons.smart_toy_outlined;
        break;
      default:
        color = Colors.grey;
        icon = Icons.help_outline;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Text(
            verdict.toUpperCase(),
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
            ),
          ),
        ],
      ),
    );
  }
}
