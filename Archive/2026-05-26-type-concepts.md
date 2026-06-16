---
type: concepts
date: '2026-05-26'
updated: '2026-05-26T10:23:30.596881+00:00'
tags:
- '#sentri'
- '#flutter'
- '#customer-profile'
- '#card-widget'
- '#freeze'
- '#ux'
lifecycle: archived
importance: 0.3535533905932738
---
# Distilled Summary
# Card Widget Freeze in Customer Profile

## Summary
Card Widget Freeze in Customer Profile

The _CardStatusWidget (customer_profile_screen.dart:1411) becomes frozen (non-tappable) under these conditions:

1. ... [Distilled] ... Card-level deactivation does NOT freeze the widget.

## Raw Logs
# Card Widget Freeze in Customer Profile

## Summary
Card Widget Freeze in Customer Profile

The _CardStatusWidget (customer_profile_screen.dart:1411) becomes frozen (non-tappable) under these conditions:

1. Customer inactive → customer.status == false (Firestore field 'customer_status')
   - isTappable = customer.status (line 1457)
   - onTap is set to null when false (line 1474)
   - Card options bottom sheet cannot be opened

2. Card deactivated independently → card.cardActive == false (Firestore field 'card_status')
   - Only affects visual gradient, NOT tappability
   - Active: dark teal gradient with green "ACTIVE" pill
   - Deactivated: grey gradient with red "DEACTIVATED" pill

3. Visual state matrix:
   | Customer Status | Card Active | Visual | Tappable |
   | Active | Active | Dark teal, green ACTIVE pill | Yes |
   | Active | Deactivated | Grey, red DEACTIVATED pill | Yes |
   | Inactive | Any | Grey gradient | No |

To restore tappability: customer must be reactivated via edit profile first. Card-level deactivation does NOT freeze the widget.