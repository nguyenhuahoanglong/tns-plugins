# PCF Controls

## Purpose

Generic PCF authoring guidance with a scoped handoff for existing Core.Component.PCF
variant deployments and browser overrides. Upstream content comes from the configured
dk-power-platform source; this skill is now owned to retain the approved routing.

## Pain Points

- Generic push/import guidance can bypass an existing project's variant and production rules.
- Installing domain skills must route operational requests without changing generic scaffolding.

## Changelog

### 2026-10-02 — Route existing control operations

Active intent r1: preserve generic authoring, route Core.Component.PCF deploy/override
to their dedicated skills, and keep production CI/CD-only. This is the user's approved
Option A integration. Ownership changes from mirror to owned so sync preserves routing.
Validation: skill-creator structure/intent checks and package routing inspection are
recorded with the team-PCF implementation report; live tool behavior is separate.
