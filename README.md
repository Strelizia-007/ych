# 🎬 TMDB Telegram Poster Bot

> **Automated movie & series content posting bot with TMDB integration, smart anime detection, and dual-channel management**

A powerful Telegram bot that transforms raw movie/series file information into beautifully formatted channel posts with automatic TMDB metadata enrichment, poster previews, and intelligent content routing.

---

## ✨ Features

### 🎯 **Core Functionality**
- **TMDB Integration** — Search and auto-fetch metadata (title, year, posters) from The Movie Database
- **Smart Content Parsing** — Automatically extracts filenames, sizes, and download links from raw text
- **Dual Channel Support** — Separate channels for anime content vs. live-action films/series
- **Auto-Backup** — Silently forwards posts to backup channels without "Forwarded from" tags
- **Rich Previews** — Embeds TMDB landscape posters as clickable hyperlinks in posts
- **MongoDB Persistence** — Stores all posts for easy retrieval and searching

### 🤖 **Intelligent Automation**
- **Anime Detection** — Uses TMDB genre IDs + origin country to auto-route anime to dedicated channel
- **Auto-Season Labeling** — Generates S01, S02, S03... filenames for multi-season series
- **Platform Tag Extraction** — Detects streaming platforms (Netflix, Amazon, etc.) from filenames
- **Flexible Audio Input** — Add audio languages or skip with one button press

### 🎨 **Beautiful Formatting**
- **Spoiler Watermarks** — Group credits hidden behind tap-to-reveal spoiler tags
- **Bold + Monospace** — Professional typography (bold text, monospaced file sizes)
- **Blockquote Audio** — Audio languages styled as quoted blocks
- **Emoji Icons** — 🦁 for headers, 🏷️ for filenames, 📥 for downloads, 🔊 for audio

---

## 📦 Installation

### Prerequisites
- Python 3.10+
- MongoDB instance (local or cloud)
- Telegram Bot Token ([create one via @BotFather](https://t.me/BotFather))
- TMDB API Key ([get free API key](https://www.themoviedb.org/settings/api))

### Quick Start

```bash
# Clone the repository
git clone <your-repo-url>
cd telegram-poster-bot

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Fill in your credentials

# Run the bot
python bot.py
```

### Environment Variables

```bash
# Telegram Configuration
BOT_TOKEN=your_telegram_bot_token
CHANNEL_FILMS=-1001234567890      # Main films/series channel
CHANNEL_ANIME=-1001234567891      # Anime-dedicated channel
DEFAULT_CHNL_FILMS=-1001234567892 # Backup channel (films)
DEFAULT_CHNL_ANIMES=-1001234567893 # Backup channel (anime)

# TMDB API
TMDB_API_KEY=your_tmdb_api_key

# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=telegram_poster_bot

# Admin Access
ADMINS=123456789,987654321  # Comma-separated Telegram user IDs
```

---

## 🚀 Usage

### Posting Movies

```
1️⃣ /tmdb Inception
   → Bot searches TMDB, shows result buttons

2️⃣ Select movie from list
   → Bot downloads poster, asks for content

3️⃣ Paste raw content:
   Inception.2010.1080p.NF.WEB-DL.DDP5.1.H.265-LioN.mkv [3.2 GB]
   https://gdflix.dev/file/abc123

4️⃣ Enter audio languages:
   Eng, Hin, Tel
   (or press "⏭️ Skip & Post" button)

5️⃣ Preview → Click "✅ Post to Channel"
   → Posted with TMDB poster preview!
```

### Posting Series

```
1️⃣ /tmdb Breaking Bad
   → Select series from TMDB results

2️⃣ Paste base name + season links:
   Breaking.Bad.S01.1080p.AMZN.WEB-DL.DDP5.1.H.265-LioN
   https://gdflix.dev/pack/season1
   https://gdflix.dev/pack/season2
   https://gdflix.dev/pack/season3

3️⃣ Bot auto-generates:
   - S01, S02, S03 labels
   - Numbered entries (unless single season)

4️⃣ Add audio → Preview → Post ✅
```

### Searching Posts

```
/fetch Breaking Bad
→ Shows all saved posts matching "Breaking Bad"
  with full content, timestamps, and embedded previews
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Telegram Bot                         │
│  ┌───────────┐  ┌──────────┐  ┌────────────────────┐  │
│  │  /tmdb    │→ │  Parser  │→ │  Formatter         │  │
│  │  /fetch   │  │          │  │  (Bold + Spoilers) │  │
│  └───────────┘  └──────────┘  └────────────────────┘  │
│        ↓              ↓                   ↓             │
│  ┌───────────────────────────────────────────────────┐ │
│  │          TMDB Client (Metadata + Posters)         │ │
│  └───────────────────────────────────────────────────┘ │
│        ↓              ↓                   ↓             │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │
│  │ Channel  │  │ Backup   │  │  MongoDB           │  │
│  │ (Films)  │  │ Channels │  │  (Persistence)     │  │
│  │ (Anime)  │  │          │  │                    │  │
│  └──────────┘  └──────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Components

| File | Purpose |
|------|---------|
| `bot.py` | Main bot logic, command handlers, state machine |
| `parser.py` | Raw text → structured data (filenames, sizes, links) |
| `formatter.py` | Structured data → beautifully formatted posts |
| `tmdb_client.py` | TMDB API integration (search, posters, metadata) |
| `db.py` | MongoDB operations (save, fetch, query) |
| `config.py` | Environment variable validation & loading |

---

## 🎭 Post Format Examples

### Movie Post
```
🦁 Inception (2010)

1. 📁 Inception.2010.1080p.NF.WEB-DL.DDP5.1.H.265-LioN.mkv
   📏 Size: 3.2 GB
   🔗 https://gdflix.dev/file/abc123

2. 📁 Inception.2010.720p.NF.WEB-DL.DDP5.1.H.264-LioN.mkv
   📏 Size: 1.8 GB
   🔗 https://gdflix.dev/file/def456

🔊 : Eng, Hin, Tel

[spoiler]@LioNriPs[/spoiler]
```

### Series Post (Multi-Season)
```
🦁 Breaking Bad (2008)

1. 🏷️ Breaking.Bad.S01.1080p.AMZN.WEB-DL.DDP5.1.H.265-LioN
   📥 https://gdflix.dev/pack/season1

2. 🏷️ Breaking.Bad.S02.1080p.AMZN.WEB-DL.DDP5.1.H.265-LioN
   📥 https://gdflix.dev/pack/season2

3. 🏷️ Breaking.Bad.S03.1080p.AMZN.WEB-DL.DDP5.1.H.265-LioN
   📥 https://gdflix.dev/pack/season3

🔊 : Eng

[spoiler]@LioNriPs[/spoiler]
```

---

## 🤖 How It Works

### State Machine Flow

```
┌──────────────┐
│  /tmdb query │
└──────┬───────┘
       ↓
┌──────────────────┐
│ TMDB Search      │ → Shows result buttons
│ (up to 10 hits)  │
└──────┬───────────┘
       ↓
┌──────────────────┐
│ User Picks Title │ → Downloads poster, detects anime
└──────┬───────────┘
       ↓
┌──────────────────┐
│ WAIT_CONTENTS    │ → User pastes filenames + links
└──────┬───────────┘
       ↓
┌──────────────────┐
│ WAIT_AUDIOS      │ → User types languages or clicks "Skip & Post"
└──────┬───────────┘
       ↓
┌──────────────────┐
│ PREVIEW          │ → Buttons: [Post] [Go Back] [Cancel]
└──────┬───────────┘
       ↓
┌──────────────────┐
│ POST TO CHANNEL  │ → Saves to MongoDB, forwards to backup
└──────────────────┘
```

### Anime Detection Logic

```python
TMDB Genre ID 16 = Animation
→ Auto-routes to CHANNEL_ANIME

Origin Country = "JP" (Japan)
→ Treats as anime even without Animation genre

Watermark:
- Anime → @PiRaTe_RiPs
- Films/Series → @LioNriPs
```

---

## 🛠️ Advanced Features

### Platform Tag Extraction
Automatically detects streaming platforms from filenames:
- `NF` → Netflix
- `AMZN` → Amazon Prime
- `HMAX` → HBO Max
- `DSNP`/`DIS+` → Disney+
- And 10+ more...

### Backup Channel Forwarding
- Every post automatically copies to backup channels
- Uses `copy_message` (not `forward_message`) to avoid "Forwarded from" tags
- Separate backup channels for anime vs. films

### Persistent Storage Schema
```javascript
{
  title: "Inception",
  type: "movie",  // or "tv"
  text: "🦁 Inception (2010)\n...",  // full formatted post
  platform_tag: "NF",
  group_name: "LioN",
  audios: "Eng, Hin, Tel",
  tmdb_title: "Inception",
  tmdb_year: "2010",
  channel_message_id: 12345,
  anime: false,
  posted_at: ISODate("2026-02-05T03:50:35.633Z")
}
```

---

## 🎨 Customization

### Change Watermarks
Edit `formatter.py`:
```python
_GROUP_FILMS = "YourGroupName"
_GROUP_ANIME = "YourAnimeGroup"
```

### Add New Platform Tags
Edit `parser.py`:
```python
_PLATFORM_RE = re.compile(
    r"(NF|AMZN|YOUR_TAG|...)"
)
```

### Modify Post Format
Edit `formatter.py` functions:
- `format_movie_post()` — Movie formatting
- `format_series_post()` — Series formatting

---

## 📝 Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/tmdb <title>` | Search TMDB & start posting flow | `/tmdb Inception` |
| `/fetch <title>` | Search saved posts in database | `/fetch Breaking Bad` |

---

## 🔒 Security Notes

- **Admin-only commands** — `/tmdb` and `/fetch` require user ID in `ADMINS` list
- **Spoiler watermarks** — Group credits hidden to prevent scraping
- **Environment variables** — Sensitive credentials never hardcoded
- **Rate limiting** — TMDB client includes timeout controls

---

## 🐛 Troubleshooting

### Bot doesn't respond
```bash
# Check bot is running
ps aux | grep bot.py

# Check logs for errors
tail -f bot.log
```

### MongoDB connection failed
```bash
# Verify MongoDB is running
sudo systemctl status mongod

# Test connection
mongo --eval "db.version()"
```

### TMDB images not showing
- Verify `TMDB_API_KEY` is correct
- Check if `disable_web_page_preview=False` in bot.py
- Ensure channel has web preview enabled

### Posts going to wrong channel
- Double-check `CHANNEL_FILMS` vs `CHANNEL_ANIME` in `.env`
- Verify bot is admin in both channels
- Check anime detection logic in `tmdb_client.py`

---

# 🎲 Quiz/Trivia Bot Integration Guide

Complete quiz/trivia system that integrates seamlessly with your existing poster bot.

---

## 📋 Overview

The Quiz Bot automatically posts trivia questions about movies and anime to separate groups, tracks user answers, awards points, and maintains daily/weekly/monthly leaderboards.

### ✨ Key Features

- **Automated Posting** — Posts quizzes every X hours (configurable)
- **Category Separation** — Movies go to movie group, anime to anime group
- **Points System** — 10 points per correct answer
- **Leaderboards** — Daily, weekly, and monthly rankings
- **TMDB Integration** — Generates dynamic questions from real movie/anime data
- **Poll Format** — Uses Telegram's native poll feature with 4 options
- **Auto-Cleanup** — Optionally deletes previous poll before posting new one
- **User Stats** — Personal statistics tracking accuracy and points

---

## 📦 Installation

### 1. Add New Files

Place these files in your bot directory:
```
quiz_bot.py          # Quiz system logic
db_quiz.py           # MongoDB operations for quizzes
bot_integrated.py    # Combined poster + quiz bot
```

### 2. Update config.py

Add these lines to your `config.py`:

```python
# ── Quiz/Trivia Groups ──────────────────────────
MOVIEGRP: str = _require("MOVIEGRP")             # Movie quiz group ID
ANIMEGRP: str = _require("ANIMEGRP")             # Anime quiz group ID

# ── Quiz Settings ───────────────────────────────
QTIME: int = int(os.getenv("QTIME", "6"))        # Quiz interval in hours
DELPREVIOUSPOLL: bool = os.getenv("DELPREVIOUSPOLL", "TRUE").upper() == "TRUE"
QUIZ_ENABLED: bool = os.getenv("QUIZ_ENABLED", "TRUE").upper() == "TRUE"
```

### 3. Update .env

Add these variables to your `.env` file:

```bash
# ─── Quiz/Trivia Settings ───────────────────────
MOVIEGRP=-1001234567894          # Movie quiz group ID
ANIMEGRP=-1001234567895          # Anime quiz group ID
QTIME=6                          # Post quiz every 6 hours
DELPREVIOUSPOLL=TRUE             # Delete previous poll before posting new one
QUIZ_ENABLED=TRUE                # Enable/disable quiz system
```

### 4. Run the Integrated Bot

**Option A: Run both systems together**
```bash
python bot_integrated.py
```

**Option B: Run quiz bot separately**
```bash
# Terminal 1: Poster bot
python bot.py

# Terminal 2: Quiz bot (standalone)
python quiz_bot.py
```

---

## 🎮 User Commands

### For Everyone

| Command | Description | Example |
|---------|-------------|---------|
| `/leaderboard` | Show daily leaderboard (all categories) | `/leaderboard` |
| `/leaderboard daily movie` | Show daily movie leaderboard | `/leaderboard daily movie` |
| `/leaderboard weekly anime` | Show weekly anime leaderboard | `/leaderboard weekly anime` |
| `/leaderboard monthly all` | Show monthly combined leaderboard | `/leaderboard monthly all` |
| `/mystats` | Show your personal quiz statistics | `/mystats` |

### For Admins

| Command | Description |
|---------|-------------|
| `/postquiz` | Manually trigger quiz posting now |
| `/quiz_enable` | Instructions to enable quiz system |
| `/quiz_disable` | Instructions to disable quiz system |

---

## 📊 How It Works

### Quiz Flow

```
1️⃣ Scheduled Timer (every QTIME hours)
   ↓
2️⃣ Generate Movie Quiz (from TMDB)
   ↓
3️⃣ Post to MOVIEGRP as Poll
   ↓
4️⃣ Generate Anime Quiz (from TMDB)
   ↓
5️⃣ Post to ANIMEGRP as Poll
   ↓
6️⃣ Wait for User Answers
   ↓
7️⃣ Award Points (10 per correct answer)
   ↓
8️⃣ Update Leaderboards
```

### Question Types

**Movie Questions:**
- Release year
- Director
- Genre
- Tagline → movie title matching

**Anime Questions:**
- First air year
- Genre
- Tagline → anime title matching

---

## 🏆 Points & Leaderboards

### Points System
- ✅ Correct answer: **10 points**
- ❌ Wrong answer: **0 points**
- Users can only answer each quiz once

### Leaderboards

**Daily** — Last 24 hours  
**Weekly** — Last 7 days  
**Monthly** — Last 30 days

Each leaderboard shows:
- Top 10 users
- Total points
- Correct/total answers ratio
- 🥇🥈🥉 medals for top 3

---

## ⚙️ Configuration

### QTIME (Quiz Interval)
How often quizzes are posted (in hours):
```bash
QTIME=6   # Every 6 hours (recommended)
QTIME=12  # Every 12 hours
QTIME=24  # Once per day
```

### DELPREVIOUSPOLL
Whether to delete the previous poll before posting a new one:
```bash
DELPREVIOUSPOLL=TRUE   # Clean groups (recommended)
DELPREVIOUSPOLL=FALSE  # Keep all polls
```

### QUIZ_ENABLED
Master switch for the entire quiz system:
```bash
QUIZ_ENABLED=TRUE   # Quizzes active
QUIZ_ENABLED=FALSE  # Quizzes disabled
```

---

## 🗄️ Database Schema

### Collections

**quizzes** — Posted quiz data
```javascript
{
  group_id: "-1001234567894",
  message_id: 12345,
  poll_id: "5472518066516754435",
  question: "🎬 In which year was 'Inception' released?",
  correct_answer: "2010",
  options: ["2010", "2009", "2011", "2012"],
  category: "movie",
  tmdb_id: 27205,
  posted_at: ISODate("2026-02-05T12:00:00Z")
}
```

**quiz_answers** — User answers
```javascript
{
  poll_id: "5472518066516754435",
  user_id: 123456789,
  username: "john_doe",
  is_correct: true,
  points: 10,
  category: "movie",
  answered_at: ISODate("2026-02-05T12:05:23Z")
}
```

---

## 🎯 Usage Examples

### Leaderboard Output

```
📅 DAILY LEADERBOARD - MOVIE

🥇 alice_wonder — 80 pts (8/10 correct)
🥈 bob_builder — 70 pts (7/9 correct)
🥉 charlie_cat — 60 pts (6/8 correct)
4. dave_dragon — 50 pts (5/7 correct)
5. eve_eagle — 40 pts (4/6 correct)
```

### User Stats Output

```
📊 Your Quiz Statistics

🎬 Movies:
   Correct: 12/15
   Points: 120

📺 Anime:
   Correct: 8/10
   Points: 80

🏆 Overall:
   Correct: 20/25
   Points: 200
   Accuracy: 80.0%
```

---

## 🔧 Troubleshooting

### Quizzes not posting

**Check:**
1. `QUIZ_ENABLED=TRUE` in `.env`
2. Bot has admin rights in both groups
3. Group IDs are correct (include the `-100` prefix)
4. TMDB API key is valid

**Test manually:**
```bash
# Send /postquiz command as admin
/postquiz
```

### Points not updating

**Check:**
1. Polls must be set to "Quiz" type (not regular poll)
2. `is_anonymous=False` is set in poll
3. MongoDB connection is working
4. Check logs for errors

### Leaderboard empty

**Wait for:**
- At least one quiz to be posted
- At least one user to answer
- Time period to match (daily = last 24h)

---

## 📝 Advanced Customization

### Add Custom Question Types

Edit `quiz_bot.py` → `generate_movie_quiz()`:

```python
elif q_type == "cast":
    # Get top cast
    credits = await _fetch_tmdb(f"movie/{movie['id']}/credits")
    cast = [c["name"] for c in credits.get("cast", [])[:5]]
    
    if not cast:
        return None
    
    correct = cast[0]  # Lead actor
    # ... generate wrong answers ...
```

### Change Points Values

Edit `quiz_bot.py` → `handle_poll_answer()`:

```python
points = 10 if is_correct else 0  # Change these values
```

### Custom Leaderboard Periods

Edit `db_quiz.py` → `get_leaderboard()`:

```python
if period == "daily":
    threshold = now - timedelta(days=1)
elif period == "weekly":
    threshold = now - timedelta(weeks=1)
elif period == "custom":  # Add new period
    threshold = now - timedelta(days=3)
```

---

## 🚀 Future Enhancements

Potential features to add:

- [ ] Streak bonuses (consecutive correct answers)
- [ ] Achievement badges
- [ ] Quiz difficulty levels
- [ ] Multiplayer challenges
- [ ] Timed quizzes with bonus points
- [ ] Image-based questions
- [ ] User-submitted questions
- [ ] Quiz categories (80s movies, sci-fi, etc.)

---

## 📄 License

Same as main bot - MIT License

---

## 🙏 Credits

- **TMDB API** — Movie & TV metadata
- **python-telegram-bot** — Telegram Bot framework
- **MongoDB** — Data persistence

---

<div align="center">

**Quiz Bot Ready! 🎉**

Add some fun and engagement to your movie/anime community!

</div>

## 📚 Dependencies

```
python-telegram-bot>=20.0  # Telegram Bot API wrapper
httpx>=0.24                # Async HTTP client for TMDB
motor>=3.0                 # Async MongoDB driver
pymongo>=4.0               # MongoDB Python driver
python-dotenv>=1.0         # Environment variable management
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 🙏 Acknowledgments

- **TMDB** — Movie & TV metadata
- **python-telegram-bot** — Excellent Telegram Bot framework
- **MongoDB** — Flexible document storage

---

<div align="center">

**Made with ❤️ for the content sharing community**

</div>
