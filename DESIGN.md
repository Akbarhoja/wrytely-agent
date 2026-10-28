---
version: alpha
name: Wrytely student workspace
description: A quiet academic workspace that makes delegated work and student control legible.
colors:
  primary: "#24664f"
  background: "#f6f8f7"
  surface: "#ffffff"
  text: "#203b34"
  muted: "#64736d"
  border: "#e0e7e3"
  tint: "#e9f2ed"
  sidebar: "#eef3f0"
  danger: "#9b3935"
typography:
  body:
    fontFamily: '"Plus Jakarta Sans Variable", sans-serif'
    fontSize: "14px"
    lineHeight: "1.6"
rounded:
  DEFAULT: "8px"
  panel: "12px"
omitted:
  - section: spacing
    reason: Existing CSS owns responsive geometry; this feature introduces no global spacing scale.
components:
  button: {}
  connection-panel: {}
---

# Wrytely design context

## Overview

This records the existing implementation, not a rebrand. The work-first overview
is the primary screen. The Connections view helps a student understand exactly
what is connected, what needs verification, and when their agent may contact them.
Think of a well-kept semester planner: work is grouped for action and the student's
choices remain clear. Avoid promotional dashboards, fictional tasks, invented
success metrics, decorative progress and generic claims of productivity.

Audience: college students, English UI, desktop and phone use. This is a product
surface; scanning, recovery and account privacy lead. Later marketing work may
explore its own expression without replacing this interface as a side effect.

## Colors

Canonical source: `web/app/globals.css :root`. This document mirrors its accepted
values (Model B); it does not generate a separate theme. Primary maps to `--green`,
background to `--bg`, surface to `--surface`, text to `--text`, muted to `--muted`,
border to `--border`, tint to `--tint`, sidebar to `--sidebar`, danger to `--danger`.
Focus uses `--focus`, matching primary. New surfaces consume these variables.
Status always includes text; green alone cannot mean that verification succeeded.
Only the existing light theme is supported in this increment.

## Typography

Self-hosted Plus Jakarta Sans is the existing voice for headings, prose and
controls. Hierarchy comes from scale/weight and spacing. Do not introduce a new
font for a single form. Use readable input text and explicit visible labels.
Codes use the same type; monospace is not a general visual identity.

## Layout

Reuse the sidebar, topbar and natural document scrolling. The Connections view
places the WhatsApp connection before future course integrations. Verification is
a real sequence, so an ordered list is appropriate. Put timing preferences in a
separate section, and separate disconnect controls from primary actions. Stack
on phones; long destination/code/error text wraps without horizontal overflow.

## Elevation & Depth

Use the incumbent white panel, 1px semantic border and restrained rounding.
No additional card shadow or nested decorative cards. Phosphor is the icon family.
Motion is functional feedback; respect the existing reduced-motion treatment.

## Shapes

Reuse 8px controls and 12px panels. Native select popup geometry is explicitly
accepted for quiet-hour choices; standard OS keyboard behavior is desirable.
Inputs, selection and focus follow the same green palette.

## Components

Canonical map for this scoped feature:

| Capability | Owner | Behavior |
|---|---|---|
| Auth/account | Clerk entry + backend verified identity | Account changes remount private UI |
| API transport | `web/lib/client.ts`, `forward.ts` | Same-origin, no cache, explicit route allowlist |
| Connection actions | `whatsapp-connection.tsx` | Server-confirmed ownership; unknown stays unknown |
| Form | Connection preference form | Explicit save, native labels, inline validation, retain unsaved input |
| Select | Native `<select>` | OS-owned popup; integer hours 0–23 |
| Confirmation | Inline disconnect group | Name queued-reply cancellation; Cancel is always available |
| Feedback | Existing inline banner/status pattern | Persistent correction text; no browser dialogs |
| Scrolling | Global stylesheet | Visible scrollbars and document flow |

Consent defaults to an unsaved false choice; suggested timezone/hours are drafts,
never implied server preferences. No autosave for permissions. Secrets stay masked
until explicitly revealed and are never persisted. Uncertain mutations require
an authoritative status check; never silently replay a code request or disconnect.
Codes are cleared on expiry or account change. No fabricated connection counts.

## Do's and Don'ts

- Name the action: Create verification code, Check connection, Save preferences.
- Explain the consequence and recovery; avoid infrastructure names in student copy.
- Preserve the existing work overview and unrelated screens.
- Show incoming-provider acceptance, delivery and uncertainty as different evidence.
- Verify keyboard use, error recovery and phone layout before calling a flow done.
