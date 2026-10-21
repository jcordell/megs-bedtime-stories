#!/usr/bin/env python3
"""Build public/episodes.json from the public Stuff You Should Know RSS feed.

Uses titles and show notes only. Official transcript URLs are linked, not copied.
"""

from __future__ import annotations

import email.utils
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

RSS_URL = (
    "https://www.omnycontent.com/d/playlist/"
    "e73c998e-6e60-432f-8610-ae210140c5b1/"
    "a91018a4-ea4f-4130-bf55-ae270180c327/"
    "44710ecc-10bb-48d1-93c7-ae270180c33e/podcast.rss"
)
ORG_ID = "e73c998e-6e60-432f-8610-ae210140c5b1"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "episodes.json"

PODCAST = "https://podcastindex.org/namespace/1.0"
ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"

# Topic labels are matched with word-boundary regexes against title + show notes.
TOPICS: list[tuple[str, str]] = [
    (
        "space",
        r"\b(space|nasa|astronauts?|planets?|mars|jupiter|saturn|venus|pluto|asteroids?|"
        r"comets?|galax(?:y|ies)|black holes?|solar system|satellites?|cosmos|hubble|"
        r"rockets?|apollo|moon landing|astronomy|orbit|milky way|eclipse)\b",
    ),
    (
        "animals",
        r"\b(animals?|dogs?|cats?|birds?|insects?|bees?|ants?|spiders?|sharks?|whales?|"
        r"dinosaurs?|snakes?|horses?|cows?|pigs?|fish|fishes|octopus|octopi|lions?|"
        r"tigers?|bears?|wolves|wolf|elephants?|monkeys?|apes?|mammals?|reptiles?|"
        r"amphibians?|zoos?|pets?|penguins?|owls?|eagles?|butterflies|caterpillars?|"
        r"mosquitoes|mosquitos|rats?|mice|mouse|bats?|frogs?|crocodiles?|alligators?|"
        r"dolphins?|coral|jellyfish|squid|beavers?|squirrels?|deer|moose|bison|"
        r"chickens?|turkeys?|honeybees?|wasps?|termites|locusts?|whales?|narwhals?|"
        r"platypus|kangaroos?|koalas?|pandas?|gorillas?|chimps?|chimpanzees?|"
        r"snails?|slugs?|sardines?|anchovies|oysters?|clams?|crabs?|lobsters?)\b",
    ),
    (
        "nature",
        r"\b(oceans?|seas?|mountains?|volcanoes?|volcanic|earthquakes?|weather|"
        r"hurricanes?|tornadoes?|climate|forests?|trees?|plants?|flowers?|rivers?|"
        r"deserts?|glaciers?|rain|snow|lightning|thunder|clouds?|geolog\w*|minerals?|"
        r"diamonds?|caves?|islands?|wetlands?|ecosystems?|environment\w*|wilderness|"
        r"waterfalls?|lakes?|tsunamis?|floods?|droughts?|wildfires?|rocks?|soil|"
        r"dirt|sand|grass|weeds?|fungi|mushrooms?|moss|seeds?|photosynthesis|"
        r"national parks?|rainforests?|jungles?|coral reefs?|tides?|waves)\b",
    ),
    (
        "food",
        r"\b(foods?|cooking|cooks?|recipes?|coffee|beers?|wines?|chocolate|cheeses?|"
        r"breads?|sugars?|spices?|restaurants?|cuisines?|breakfasts?|pizzas?|"
        r"whiskey|whisky|teas?|sodas?|coca-cola|barbecue|bbq|candy|desserts?|"
        r"ice cream|burgers?|sandwiches|kitchens?|farming|agriculture|crops?|"
        r"wheat|corn|rice|salt|pepper|vanilla|cinnamon|honey|maple syrup|"
        r"fermentation|yeast|beer|alcohol|cocktails?|bourbon|rum|vodka|gin|"
        r"champagne|fast food|junk food|nutrition|calories|vitamins?|dieting|"
        r"vegetarian|vegan|meat|bacon|sushi|noodles?|pasta|ketchup|mustard|"
        r"pies?|chopsticks|barbecue|dumplings?|tacos?|burritos?)\b",
    ),
    (
        "body",
        r"\b(bodies|body|brains?|hearts?|blood|bones?|muscles?|skin|eyes?|ears?|"
        r"teeth|tooth|hair|organs?|livers?|kidneys?|lungs?|stomachs?|intestines?|"
        r"hormones?|genes|genetic\w*|dna|viruses?|diseases?|cancers?|medicine|"
        r"doctors?|surgery|vaccines?|immune|pregnan\w*|babies|baby|birth|anatomy|"
        r"skeletons?|sleep|dreams?|dreaming|allerg(?:y|ies)|pain|fever|flu|"
        r"bacteria|microbes?|gut|digestion|breathing|lungs?|vision|hearing|"
        r"taste|smell|aging|ageing|puberty|menstruat\w*|sperm|ovaries|uterus|"
        r"placenta|twins|cloning|placebo|addiction|drugs?|opioids?|nicotine|"
        r"alcoholism|obesity|diabetes|alzheimer'?s|dementia|autism|adhd|"
        r"narcolepsy|birthmarks?|knuckles?|bras?|hiccups?|yawns?|"
        r"sneez\w*|coughs?|headaches?|migraines?|concussions?)\b",
    ),
    (
        "mind",
        r"\b(psycholog\w*|brains?|dreams?|dreaming|memories|memory|phobias?|"
        r"placebos?|bias(?:es)?|personality|consciousness|subconscious|"
        r"emotions?|anxiety|depression|mental|therapy|freud|jung|iq\b|"
        r"intelligence|habits?|motivation|happiness|boredom|fear|laughter|"
        r"crying|love|attraction|jealousy|anger|stress|ptsd|trauma|"
        r"optical illusions?|perception|deja vu|sleep|insomnia|hypnosis|"
        r"meditation|mindfulness|ocd|schizophren\w*|bipolar|sociopath\w*|"
        r"psychopath\w*|empathy|morality|ethics|free will|decision)\b",
    ),
    (
        "science",
        r"\b(science|scientists?|experiments?|physics|chemistry|atoms?|quantum|"
        r"electricity|magnets?|magnetic|gravity|evolution|biology|elements?|"
        r"periodic table|lasers?|math|mathematics|statistics|molecules?|"
        r"particles?|relativity|einstein|newton|darwin|laborator\w*|"
        r"scientific|thermodynamics|entropy|radioactiv\w*|nuclear|"
        r"chemicals?|plastics?|polymers?|glass|concrete|steel|alloys?|"
        r"invent(?:ed|ion|or|ors)?|engineering|bpas?)\b",
    ),
    (
        "technology",
        r"\b(computers?|internet|software|phones?|smartphones?|artificial intelligence|"
        r"\bai\b|robots?|robotics|engines?|cars?|automobiles?|trains?|airplanes?|"
        r"aircraft|ships?|boats?|cameras?|television|tv|radios?|printing|"
        r"inventions?|inventors?|machines?|algorithms?|hacking|hackers?|"
        r"cyber\w*|satellites?|gps|bluetooth|wifi|wi-fi|email|social media|"
        r"google|apple|iphone|android|bitcoin|crypto|blockchain|3d print\w*|"
        r"drones?|submarines?|helicopters?|rockets?|batteries|electric cars?|"
        r"typewriters?|telegraphs?|telephones?|projectors?|subways?|"
        r"flight attendants?|bridges?|skyscrapers?|elevators?|escalators?)\b",
    ),
    (
        "history",
        r"\b(histor(?:y|ical|ian|ians)|ancient|medieval|centur(?:y|ies)|"
        r"civilizations?|empires?|pharaohs?|romans?|greece|greek|vikings?|"
        r"pirates?|archaeolog\w*|artifacts?|revolutions?|colonial|mummy|mummies|"
        r"pyramids?|cleopatra|napoleon|caesar|titanic|renaissance|silk road|"
        r"ottoman|byzantine|mesopotamia|aztecs?|maya|incas?|knights?|castles?|"
        r"dynast(?:y|ies)|prohibition|dust bowl|great depression|watergate|"
        r"lincoln|washington|jefferson|roosevelt|churchill|hitler|stalin|"
        r"gandhi|mandela|civil rights|slavery|underground railroad|"
        r"industrial revolution|founding fathers|declaration of independence|"
        r"constitution|salem|pilgrims?|explorers?|columbus|magellan|"
        r"world'?s fair|victorian|edwardian|bronze age|iron age|stone age|"
        r"neanderthal|homo sapiens|fossils?|blacksmiths?|shipwrecks?|"
        r"hindenburg|great britain|odyssey|iliad)\b",
    ),
    (
        "war",
        r"\b(wars?|battles?|military|army|navy|soldiers?|weapons?|bombs?|"
        r"genocide|invasions?|world war|civil war|cold war|vietnam|wwii|wwi|"
        r"troops|generals?|tanks?|submarines?|nuclear weapons?|atom bomb|"
        r"hiroshima|nagasaki|d-day|revolutionar\w* war|crusades?|"
        r"guerrilla|terroris\w*|pentagon|marines?)\b",
    ),
    (
        "politics",
        r"\b(elections?|congress|senate|democrats?|republicans?|voting|votes?|"
        r"supreme court|constitution|government|propaganda|cia|fbi|presidents?|"
        r"politics|political|white house|impeachment|campaigns?|lobbying|"
        r"democracy|dictators?|communis\w*|socialis\w*|capitalis\w*|fascis\w*|"
        r"anarchis\w*|united nations|nato|embass(?:y|ies)|ambassadors?|"
        r"legislation|laws?|illegal|legal|courts?|judges?|juries|jury|"
        r"neutrality|bar exam|constitutions?)\b",
    ),
    (
        "crime",
        r"\b(murders?|crimes?|prisons?|jail|mafia|mobsters?|serial killers?|"
        r"heists?|police|forensic\w*|poison(?:s|ed|ing)?|robber(?:y|ies)|"
        r"thieves|theft|kidnapp\w*|assassinations?|gangsters?|cartels?|"
        r"smuggl\w*|piracy|outlaws?|fbi|detectives?|sheriffs?|wanted|"
        r"death row|execution|guillotine|alcatraz|capone|bonnie and clyde|"
        r"vigilantes?)\b",
    ),
    (
        "mysteries",
        r"\b(disappearances?|unsolved|mysteries|mystery|missing|lost colony|"
        r"bermuda triangle|d\.?b\.? cooper|zodiac|jack the ripper|"
        r"who killed|vanished|unexplained|enigma)\b",
    ),
    (
        "money",
        r"\b(money|taxes|tax|econom\w*|stocks?|banks?|banking|inflation|"
        r"debts?|insurance|capitalism|gold standard|bitcoin|cryptocurrenc\w*|"
        r"wall street|recession|depression|billionaires?|millionaires?|"
        r"poverty|wealth|wages?|salar(?:y|ies)|dollar|currency|coins?|"
        r"counterfeit|federal reserve|interest rates?|mortgages?|rent|"
        r"advertising|marketing|brands?|corporations?|monopol(?:y|ies)|"
        r"trade|tariffs?|gdp|stock market|enron|co-ops?|cooperatives?|"
        r"middle class|wall street)\b",
    ),
    (
        "sports",
        r"\b(football|baseball|basketball|olympics?|soccer|hockey|boxing|"
        r"golf|tennis|athletes?|world cup|super bowl|cricket|wrestling|"
        r"nascar|formula 1|f1\b|marathon|swimming|skiing|snowboard\w*|"
        r"surfing|skateboard\w*|ufc|mma|nba|nfl|mlb|nhl|fifa|coaches?|"
        r"stadiums?|cheerlead\w*|horse racing|kentucky derby|tour de france|"
        r"wimbledon|world series|stanley cup|le mans)\b",
    ),
    (
        "music",
        r"\b(music|songs?|albums?|bands?|jazz|hip[- ]?hop|rappers?|rap\b|"
        r"beatles|instruments?|orchestras?|opera|composers?|vinyl|records?|"
        r"guitars?|pianos?|drums?|singers?|singing|concerts?|festivals?|"
        r"mozart|beethoven|bach|elvis|dylan|reggae|blues|country music|"
        r"punk|metal|disco|motown|grammy|broadway musicals?|lyrics?|"
        r"symphony|choir|banjo|violin|trumpet|saxophone)\b",
    ),
    (
        "culture",
        r"\b(movies?|films?|hollywood|television|tv shows?|celebrities|"
        r"celebrity|comics?|cartoons?|toys?|fashion|books?|novels?|authors?|"
        r"poets?|poetry|art|artists?|museums?|disney|marvel|star wars|"
        r"video games?|game shows?|broadway|theat(?:er|re)|oscars?|emmys?|"
        r"netflix|literature|shakespeare|novels?|fairy tales?|folklore|"
        r"myths?|mythology|legends?|superheroes|superhero|barbie|lego|"
        r"christmas movies?|sitcoms?|anime|manga|photography|photographs?|"
        r"painting|sculpture|architecture|buildings?|skyscrapers?|"
        r"fashion|clothing|jeans|sneakers|hats?|tattoos?|pirates?|"
        r"etiquette|m\*a\*s\*h|rockettes|porcelain|manicures?|"
        r"contortion\w*|parenting|sitcoms?)\b",
    ),
    (
        "language",
        r"\b(etymolog\w*|slang|grammar|alphabets?|languages?|linguist\w*|"
        r"dialects?|accents?|proverbs?|idioms?|spelling|punctuation|"
        r"dictionar\w*|shakespeare|words? origin|english language|"
        r"latin|greek language|hieroglyph\w*|writing systems?|cursive|"
        r"fonts?|typography|translation|translators?|sign language|"
        r"pig latin|palindromes?|anagrams?|acronyms?)\b",
    ),
    (
        "weird",
        r"\b(ufos?|aliens?|bigfoot|loch ness|ghosts?|haunt\w*|vampires?|"
        r"werewolves?|zombies?|witches?|witchcraft|magic|conspirac\w*|"
        r"illuminati|paranormal|cryptids?|monsters?|demons?|satan|"
        r"cults?|bizarre|weird|curses?|superstitions?|occult|spooky|"
        r"creepy|urban legends?|area 51|bermuda|time travel|flat earth|"
        r"sasquatch|chupacabra|yeti|nessie|ouija|seances?|exorcis\w*)\b",
    ),
    (
        "holidays",
        r"\b(christmas|halloween|thanksgiving|easter|holidays?|new year'?s?|"
        r"valentine'?s?|hanukkah|ramadan|diwali|birthday|fourth of july|"
        r"independence day|st\.? patrick|kwanzaa|passover|dia de los muertos|"
        r"carnival|mardi gras|oktoberfest|black friday|cyber monday)\b",
    ),
    (
        "religion",
        r"\b(religio\w*|christian\w*|catholic\w*|protestant\w*|jewish|judaism|"
        r"muslims?|islam\w*|hindus?|hinduism|buddhis\w*|bible|quran|koran|"
        r"church(?:es)?|mosques?|temples?|vatican|pope|saints?|gods?|"
        r"goddess(?:es)?|pray(?:er|ers|ing)?|theology|atheis\w*|agnostic|"
        r"cults?|mormons?|scientology|sikh|shinto|pagan\w*|mythology)\b",
    ),
]


def plain_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(
        r"See omnystudio\.com/listener for privacy information\.?",
        "",
        text,
        flags=re.I,
    )
    return text.strip()


def parse_duration(raw: str | None) -> int:
    if not raw:
        return 0
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    parts = raw.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 1:
        return nums[0]
    return 0


def episode_format(title: str) -> str:
    folded = title.lower().strip()
    if folded.startswith("short stuff"):
        return "short"
    if folded.startswith("selects") or folded.startswith("sysk selects"):
        return "selects"
    if "playlist" in folded[:48]:
        return "playlist"
    if folded.startswith("sysk live"):
        return "live"
    return "episode"


def label_topics(title: str, summary: str) -> list[str]:
    """Prefer the title. Show notes mention too many passing subjects."""
    title_hits = [name for name, pattern in TOPICS if re.search(pattern, title.lower())]
    if title_hits:
        return title_hits
    summary_l = summary.lower()
    return [name for name, pattern in TOPICS if re.search(pattern, summary_l)]


def fetch_rss() -> bytes:
    request = urllib.request.Request(
        RSS_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SYSKCatalog/1.0)"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main() -> None:
    root = ET.fromstring(fetch_rss())
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("RSS feed has no channel")

    episodes: list[dict] = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        if not title or not guid:
            continue
        published = item.findtext("pubDate") or ""
        try:
            when = email.utils.parsedate_to_datetime(published)
            date = when.date().isoformat()
        except (TypeError, ValueError):
            date = ""
        summary = plain_text(item.findtext("description") or "")
        duration = parse_duration(item.findtext(f"{{{ITUNES}}}duration"))
        transcript = None
        for node in item.findall(f"{{{PODCAST}}}transcript"):
            url = node.attrib.get("url") or ""
            if "TextWithTimestamps" in url or node.attrib.get("type") == "text/plain":
                transcript = (
                    f"https://api.omny.fm/orgs/{ORG_ID}/clips/{guid}/transcript"
                    "?format=TextWithTimestamps"
                )
                break
        episodes.append(
            {
                "id": guid,
                "title": title,
                "date": date,
                "duration": duration,
                "summary": summary,
                "topics": label_topics(title, summary),
                "format": episode_format(title),
                "url": (item.findtext("link") or "").strip(),
                "transcript": transcript,
            }
        )

    episodes.sort(key=lambda episode: episode["date"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(episodes, ensure_ascii=False, separators=(",", ":")))
    labeled = sum(1 for episode in episodes if episode["topics"])
    print(f"wrote {len(episodes)} episodes to {OUT}")
    print(f"labeled {labeled} ({labeled / len(episodes):.0%})")
    from collections import Counter

    counts = Counter(topic for episode in episodes for topic in episode["topics"])
    for name, count in counts.most_common():
        print(f"  {count:4} {name}")
    print("--- unlabeled sample ---")
    shown = 0
    for episode in episodes:
        if episode["topics"]:
            continue
        print(episode["title"])
        shown += 1
        if shown == 40:
            break


if __name__ == "__main__":
    main()
