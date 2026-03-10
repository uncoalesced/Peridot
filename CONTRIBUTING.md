\# CONTRIBUTING TO PERIDOT



The Peridot kernel is an open-source, sovereign AI architecture. Contributions are welcome, provided they adhere to the core philosophy: \*\*100% local, air-gapped, and zero telemetry.\*\*



\### > ARCHITECTURE RULES

1\. \*\*No Cloud Dependencies:\*\* PRs introducing external APIs (OpenAI, Anthropic, etc.) will be immediately rejected.

2\. \*\*Hardware Agnosticism:\*\* Code should default to CPU/RAM if specific GPU architectures (CUDA/ROCm) are unavailable.

3\. \*\*Medical Research:\*\* Enhancements to the Folding@home module must prioritize instant suspension upon user prompt.



\### > HOW TO CONTRIBUTE

1\. Fork the repository.

2\. Create a feature branch (`git checkout -b feature/audio-enhancement`).

3\. Commit your changes (`git commit -m 'Add ambient noise filtering to Whisper'`).

4\. Push to the branch (`git push origin feature/audio-enhancement`).

5\. Open a Pull Request referencing any related GitHub Issues.



\*\*Engineered by uncoalesced.\*\*

