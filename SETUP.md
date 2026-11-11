# SVG profile setup

This is a replacement `README.md`, **one** renderer (`scripts/render_cards.py`), a JSON cache, and an extension to the existing daily snake Action (`.github/workflows/snake.yml`). The original snake generation stays intact; additional steps refresh the JSON and SVG cards on `main`.

## Run locally

Install Inter and `fonttools` (including its `pyftsubset` command); on Ubuntu:

```bash
sudo apt-get install fonts-inter fontconfig
python -m pip install 'fonttools[woff]>=4.50,<5'
STATIC=1 python scripts/render_cards.py
```

Set `INTER_FONT=/path/to/Inter-Regular.otf` if fontconfig cannot locate Inter. All SVGs embed subsetted WOFF font bytes; no external fonts, scripts, images, or stylesheets are fetched by GitHub.

For a portrait, supply `--portrait assets/portrait.png` and commit that portrait only if you want it in the repository; the SVG embeds the image bytes, so the source can also remain local.

For local live data:

```bash
GITHUB_TOKEN=your_fine_grained_or_classic_token python scripts/render_cards.py --refresh
```

On GitHub, use **Actions → Generate contribution assets → Run workflow** after merging. It uses the default ephemeral `GITHUB_TOKEN` with `contents:write` and refreshes the last 365 days from GitHub GraphQL. GitHub's repository settings must permit Actions to write to contents, and any branch protection must permit the bot commit (otherwise use a PR workflow).

The chart counts GitHub's calendar contributions, which include commits, issues, PRs and reviews as recognized by GitHub; it is **not** a commits-only count. Streak is the number of consecutive active days ending today or yesterday (UTC), and busiest day uses the highest contribution count in the collected interval.

`STATIC=1` disables animation entirely and directly emits final-frame content for screenshots. Standard mode uses only embedded CSS keyframes and a small optional SMIL glint. Reduced-motion preferences disable all visible animation.

GitHub may cache SVGs briefly. The linked three-card row uses explicit `width="32.5%"` values; links are HTML `<a>` wrappers, not links embedded within the SVG, because SVGs loaded as `<img>` cannot provide reliable clickable regions.

## Source/theme

Source README: `CarlosEduardoLemos/CarlosEduardoLemos` (`main`). Site theme: `CarlosEduardoLemos/Site-Portifolio` (`style.css`, `index.html`). Preserved visual principles: Inter, white type, dark translucent surfaces, restrained borders and rounded corners. The site does **not** define a unique coloured brand accent; the violet accent is a chosen complement, not a sampled official hex.
