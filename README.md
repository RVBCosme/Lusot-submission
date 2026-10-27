# Lusot

Lusot reports how deep a flood is at one spot in Metro Manila, in MMDA's own gauge levels and passability classes, and it shows its evidence. Each report is a phone photo. SAM 3.1 outlines the water, the wheels and the people in it. Muse Spark 1.3 names where the water meets them, and code turns that into a level. Rim geometry adds a depth range in inches only where it passes its release gate. The result goes on a live map, and Ask Lusot answers typed or spoken Taglish questions from nearby reports. When the photo can't support a reading, Lusot says it can't tell.

> Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.

**Status:** in development for the Meta Global AI Developer Hackathon (Indie track). Everything in this repository was built during the event, from Oct 27, 2026. Progress is tracked in [docs/PROGRESS.md](docs/PROGRESS.md).

Not affiliated with MMDA.

## Repository layout

| Path | What |
|---|---|
| `app/` | React + Vite website, wrapped by Capacitor for Android |
| `backend/` | One AWS SAM template, the Node.js API Lambda and the Python analysis Lambda |
| `eval/` | Evaluation rules, written before any result was seen, and the evaluation code |
| `docs/` | Design, milestone specs and plans, the progress board, the work log and research notes |

## Development

The setup commands are added as MS1 lands. See the "Commands" section of [CLAUDE.md](CLAUDE.md).

## Credits

Every third-party starter, library, model and dataset is listed here with its licence. The list is completed as each one is added.

| Component | Use | Licence |
|---|---|---|

## How it was built

Rene Vincent Cosme built Lusot as a solo entry, with Claude Code (Anthropic) as a coding assistant.
