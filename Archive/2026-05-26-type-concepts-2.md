---
type: concepts
date: '2026-05-26'
updated: '2026-05-26T10:36:30.083132+00:00'
tags:
- '#sentri'
- '#flutter'
- '#customer-profile'
- '#card-widget'
- '#ux'
- '#updated'
lifecycle: archived
importance: 0.3535533905932738
---
# Distilled Summary
# Card Widget in Customer Profile (Updated 2026-05-26)

## Summary
Card Widget in Customer Profile (Updated 2026-05-26)

The _CardStatusWidget in customer_profile_screen.dart is now ALWAYS tappable regardless of customer status. ... [Distilled] ... Title renamed from 'Manage RFID Access' → 'Manage Card Access'

## Raw Logs
# Card Widget in Customer Profile (Updated 2026-05-26)

## Summary
Card Widget in Customer Profile (Updated 2026-05-26)

The _CardStatusWidget in customer_profile_screen.dart is now ALWAYS tappable regardless of customer status. The freeze was moved deeper:

1. Card widget itself (customer_profile_screen.dart:1455+):
   - Always tappable — opens the card options bottom sheet
   - onTap no longer checks customer.status
   - Gradient still shows dimmed when customer is inactive (visual feedback)

2. Activate/Deactivate toggle (bottom sheet, line 1772+):
   - Frozen (onTap: null, greyed icon/text) when customer is inactive
   - Shows lock icon + "Customer must be active to change card access" subtitle
   - Only the toggle option is frozen — other options (Change Assigned Card) remain tappable

3. Title renamed from 'Manage RFID Access' → 'Manage Card Access'