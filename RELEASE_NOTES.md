# Final release — changes from Cross-Platform Source

- Default video download quality: 1080p preferred rather than 720p. Best available remains a separate option.
- Fixed explicit yuv420p overlay filter graph for blurred portrait exports; improved resampling and export CRF/CQ.
- Subtitle sizing and bottom safe margin adjusted.
- Lazy CUDA library failure handled by restarting Whisper transcription on CPU.
- Retains persistent jobs, retry, platform launchers, and local-only dashboard.

## Known limitations

This is a source distribution, not a platform-signed app. GPU and Apple environments require real device testing. The background green-artifact bug is addressed in the filter pipeline, but the user's original problematic footage was not available for an exact regression test. Highlight quality remains primarily speech-based. 1080p input is not guaranteed when providers do not expose that format.
