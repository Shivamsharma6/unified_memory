---
name: Framework Connector Request
about: Propose a new adapter or connector for an AI agent framework (e.g. AutoGen, DSPy, Haystack)
title: '[CONNECTOR]: '
labels: ['enhancement', 'connector', 'help wanted']
assignees: ''
---

### Framework Name
<!-- e.g. Microsoft AutoGen, DSPy, Semantic Kernel, Haystack, Google Antigravity -->

### Motivation & Use Case
<!-- Explain why this connector would be valuable for developers and how agents in this framework will use UAMS. -->

### Proposed API / Usage Snippet
```python
# Example of how the adapter should be instantiated and used
from uams_sdk.adapters.new_framework import UAMSNewFrameworkMemory

memory = UAMSNewFrameworkMemory(...)
```

### Key Integration Touchpoints
- [ ] Short-term conversation history
- [ ] Hybrid semantic & graph retrieval
- [ ] Session lifecycle (`begin_task` / `end_task` distillation)
- [ ] Bitemporal claim updates

### Additional Context
<!-- Any documentation links, framework version constraints, or references. -->
