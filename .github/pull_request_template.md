## Summary of Changes

A concise description of the problem solved, architectural motivation, and key changes made.

## Type of Change
- [ ] 🐛 Bug fix (non-breaking change fixing an issue)
- [ ] ✨ New feature or connector (e.g. LangChain, CrewAI, AutoGen, LlamaIndex)
- [ ] 🔒 Security fix or trust boundary hardening
- [ ] ⚡ Performance optimization or index enhancement
- [ ] 📚 Documentation update or examples
- [ ] 🧪 Test suite addition

## Testing & Verification
- [ ] Ran full test suite: `python -m pytest memory_watcher/tests memory_watcher/api/tests -q`
- [ ] Python bytecode compilation clean: `python -m compileall memory_watcher uams_sdk -q`
- [ ] Dependency check clean: `python -m pip check`
- [ ] Added automated test cases under `memory_watcher/tests/`

## AGENTS.md & Vault Checklist
- [ ] No private notes, personal secrets, or local `.env` keys included.
- [ ] Vault modifications strictly adhere to [AGENTS.md](AGENTS.md) conventions.
- [ ] Changes maintain local-first, privacy-respecting defaults.
