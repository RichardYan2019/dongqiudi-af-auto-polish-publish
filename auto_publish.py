import requests
import json
import os
import re
import anthropic
from dotenv import load_dotenv

load_dotenv()
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# 球队全称 -> 简称映射（依据球队官网）
TEAM_NAME_MAP = {
    "Borussia Dortmund": "Dortmund",
    "Borrussia Dortmund": "Dortmund",
    "Internazionale": "Inter",
    "Inter Milan": "Inter",
    "FC Barcelona": "Barcelona",
    "Real Madrid CF": "Real Madrid",
    "Club Atletico de Madrid": "Atletico Madrid",
    "Atletico de Madrid": "Atletico Madrid",
    "Manchester United": "Man United",
    "Manchester City": "Man City",
    "Tottenham Hotspur": "Tottenham",
    "Newcastle United": "Newcastle",
    "Aston Villa FC": "Aston Villa",
    "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea",
    "Liverpool FC": "Liverpool",
    "FC Bayern Munich": "Bayern",
    "FC Bayern München": "Bayern",
    "Bayern Munich": "Bayern",
    "SSC Napoli": "Napoli",
    "AC Milan": "Milan",
    "Juventus FC": "Juventus",
    "AS Roma": "Roma",
    "Atalanta BC": "Atalanta",
    "Paris Saint-Germain": "PSG",
    "Paris Saint Germain": "PSG",
}

# 头部球队（触发置顶池）
TOP_TEAMS = [
    "Real Madrid", "Barcelona", "Atletico Madrid",
    "Arsenal", "Chelsea", "Man United", "Man City", "Liverpool",
    "Newcastle", "Aston Villa", "Tottenham",
    "Bayern", "Dortmund",
    "Inter", "Napoli", "Milan", "Juventus", "Roma", "Atalanta",
    "PSG",
]

cookies = {
    "auth_token": os.environ.get("AF_AUTH_TOKEN", ""),
    "laravel_session": os.environ.get("AF_LARAVEL_SESSION", ""),
    "remember_82e5d2c56bdd0811318f0cf078b78bfc": os.environ.get("AF_REMEMBER_TOKEN", ""),
    "afuid": os.environ.get("AF_UID", ""),
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://admin.allfootballapp.com/admin/dashboard",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

session = requests.Session()
session.cookies.update(cookies)
session.headers.update(headers)

# 中文后台（zh-admin），用于通过中文 ID 拉取原文翻译
zh_cookies = {
    "auth_token": os.environ.get("AF_AUTH_TOKEN", ""),
    "laravel_session": os.environ.get("AF_ZH_LARAVEL_SESSION", ""),
    "remember_82e5d2c56bdd0811318f0cf078b78bfc": os.environ.get("AF_REMEMBER_TOKEN", ""),
    "afuid": os.environ.get("AF_UID", ""),
}
zh_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://zh-admin.allfootballapp.com/dist",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
zh_session = requests.Session()
zh_session.cookies.update(zh_cookies)
zh_session.headers.update(zh_headers)

# 标准名字（球队/球员/官员/媒体），用于统一大小写和格式
STANDARD_NAMES = [
    # 球队
    "Atletico", "Villarreal", "Espanyol", "Athletic Club", "Sevilla", "Real Sociedad", "Valencia",
    "Arsenal", "Newcastle", "Fulham", "Hotspur",
    "Bayern", "Dortmund", "Leverkussen", "Hoffenheim", "Frankfurt", "FC Union Berlin",
    "Borussia Mönchengladbach", "Hamburger SV", "Wolfsburg",
    "Inter Milan", "Juventus", "Roma", "Bologna", "SS Lazio", "Atalanta", "Sassuolo",
    "PSG", "Strasbourg", "Sporting CP", "Ajax",
    "Leicester City", "Ipswich", "Hull City", "Lecce", "Bodo/Glimt",
    # 国家队
    "Germany", "S. Korea", "Switzerland", "Brazil", "Netherland", "Spain", "Portugal", "Croatia",
    # 官员、教练
    "De Laurentiis", "Florentino", "Arteta", "Guardiola", "Sir Ferguson", "Pellegrini",
    "Gasperini", "Allegri", "Mourinho", "Klopp", "Ancelotti", "Pochettino", "Emery",
    "Simone", "Zidane", "Flick", "F.Farioli", "Rosenior", "Sean Dyche", "Babbel",
    "Arbeloa", "Pocognoli", "T·Frank", "Thomas Frank",
    # 球员
    "Szczesny", "Ter Stegen", "Lewandowski", "Iniesta", "Pedro", "Rivaldo", "Carreras",
    "TAA", "Alvarez", "Marcus Thuram", "Calhanoglu", "Modric", "Saelemaekers", "Pavlovic",
    "Vlahovic", "Koopmeiners", "KDB", "Buongiorno", "Vanja", "Fabregas", "Goretzka",
    "A. Davies", "Alphonso Davies", "Upamecano", "Jobe Bellingham", "Kvaratskhelia", "Zaire-Emery", "Marquinhos",
    "Bernado Silva", "E. Martinez", "Federico Chiesa", "Szoboszlai", "Gyokeres", "Gvardiol",
    "Virgil van Dijk", "Mamardashvili", "Tosin", "Bruno Fernandes", "Lisandro Martinez",
    "Van de Ven", "Kulusevski", "Giovanni Simeone", "Pio Esposito", "Luis Suarez", "Ibrahimovic",
    "Bale", "Ramos", "Muller", "Aguero", "Courtois", "J.Rodriguez", "Giroud", "Asensio",
    "Perisic", "Hummels", "Casemiro", "Henderson", "Jorginho", "Martinelli", "David Silva",
    "Skriniar", "Kovacic", "Wijnaldum", "Andre Silva", "Smith Rowe", "Fernandinho", "Deulofeu",
    "Givairo Read", "Brajan Gruda", "Mbeumo", "Frenkie de Jong", "Luuk de Jong",
    "Rio Ngumoha", "Trey Nyoni", "Yehvann Diouf", "Ismael Saibari", "Frank Onyeka",
    "Stanley Nwabali", "Giovanni Leoni", "Mastantuono", "Sesko", "Dorgu",
    "Levante", "Huijsen", "Rodrygo", "Lammens", "Kounde", "Woltemade", "Hugo Souza",
    "Wesley Lima", "Rafael Louzán", "Filip Jorgensen", "Panichelli", "Kerim Alajbegovic",
    "Raphinha", "Koubek", "Shane Kluivert", "Pol Planas", "Jorgensen", "Joan Garcia",
    "Pubill", "Virgili", "Roefs",
    # 补充球员/教练
    "Matthäus", "Kompany",
    # 媒体
    "Mundo Deportivo", "Transfermarkt", "laSexta", "Sport",
    # 其他
    "Pitarch", "buy back clause", "EFL Cup", "Euro", "UEFA European Championship", "Bardghji",
    # 补充球员（英超/西甲/德甲/意甲/法甲）
    "Dimitrievski", "Foulquier", "Gaya", "Saravia", "Santamaria", "L.Rioja", "Diakhaby",
    "G. Rodriguez", "Cömert", "Núñez", "Sadiq", "Pepelu", "Danjuma", "Raba", "A. Almeida",
    "Ugrinic", "Rivero", "Copete", "Hugo Duro", "Thierry R", "Vázquez", "Ramazani",
    "Beltrán", "Agirrezabala", "Requeni", "López", "Javi Guerra",
    "Alaba", "Carvajal", "Rüdiger", "F. Mendy", "D. Ceballos", "Trent", "Mbappe",
    "Valverde", "E. Militao", "Brahim", "Lunin", "Fran García", "Tchouameni", "Vini Jr.",
    "Camavinga", "Bellingham", "Manuel Ángel", "Arda Güler", "A. Carreras", "Gonzalo",
    "Asencio", "Fran González", "Cestero", "Thiago", "Cancelo", "Christensen", "Olmo",
    "F. De Jong", "Rashford", "Ferran", "R. Araujo", "Eric", "Pedri", "Balde", "M. Casado",
    "Gavi", "Fermín", "Roony", "Lamine Yamal", "Gerard Martín", "Cubarsí", "Kochen",
    "Bernal", "Jofre", "Yuri", "Laporte", "Galarreta", "Y. Álvarez", "I. Lekue", "Williams",
    "Gorosabel", "Vesga", "Berenguer", "Unai Simón", "Guruzeta", "Areso", "Vivian",
    "Navarro", "O. Sancet", "Paredes", "Prados", "Williams Jr", "Nico Serrano",
    "Nørgaard", "Trossard", "Kepa", "Raya", "Ødegaard", "Merino", "Jesus", "Rice",
    "Gyökeres", "Gabriel", "Havertz", "Ben White", "Eze", "Zubimendi", "Saliba", "Saka",
    "Madueke", "Timber", "Calafiori", "Hincapie", "Mosquera", "Lewis-Skelly", "Dowman",
    "Adarabioyo", "Cucurella", "Chalobah", "Reece James", "Sánchez", "Pedro Neto",
    "Badiashile", "Palmer", "Fofana", "Mudryk", "Jørgensen", "Enzo", "Słonina",
    "Caicedo", "Colwill", "Gusto", "Garnacho", "Delap", "Wiley", "Gittens", "Lavia",
    "Essugo", "Sharman-Lowe", "Sarr", "Hato", "Santos", "Acheampong", "Estêvão", "Guiu",
    "Heaton", "Maguire", "Shaw", "Mount", "Mazraoui", "Bayındır", "De Ligt", "Dalot",
    "Ugarte", "Cunha", "Malacia", "Zirkzee", "Amad Diallo", "Mainoo", "Fredricson",
    "Yoro", "Obi", "Heaven", "León", "Alisson", "Endo", "Salah", "Robertson", "Woodman",
    "Gomez", "Jota", "Konate", "Isak", "Gakpo", "Mac Allister", "Curtis Jones",
    "Gravenberch", "Frimpong", "Ramsay", "Ekitiké", "Bradley", "Kerkez",
    "Wirtz", "Bajcetic", "Ruddy", "Trippier", "Schar", "Burn", "Gillespie", "Krafth",
    "Pope", "Wissa", "J.Murphy", "Joelinton", "Ramsdale", "Barnes", "Willock", "Tonali",
    "Gordon", "Livramento", "Botman", "Thiaw", "Elanga", "Ramsey", "Hall", "Osula",
    "A.Murphy", "Miley", "Lindelof", "Bizot", "Digne", "Barkley", "McGinn", "Mings",
    "Tielemans", "Watkins", "Buendia", "Abraham", "Bailey", "P. Torres", "Kamara",
    "Konsa", "Cash", "Douglas Luiz", "Sancho", "Rogers", "Onana", "Elliott", "Maatsen",
    "Bogarde", "García", "Alysson", "Cairney", "Leno", "Lecomte", "Raul Jimenez", "Tete",
    "Andersen", "Iwobi", "Lukic", "Castagne", "Reed", "Harry Wilson", "Diop", "Berge",
    "Robinson", "Chukwueze", "Sessegnon", "Cuenca", "Bassey", "Bobb", "Muniz", "Kevin",
    "Kusi-Asare", "King", "Coleman", "Gueye", "Pickford", "Tarkowski", "Keane", "Grealish",
    "Travers", "Dewsbury-Hall", "Mykolenko", "McNeil", "Garner", "Beto", "Ndiaye",
    "Branthwaite", "Patterson", "Alcaraz", "O'Brien", "Iroegbunam", "Röhl", "Dibling",
    "George", "Barry", "Aznou", "Armstrong", "Ben Davies", "Palhinha", "Maddison",
    "Solanke", "Vicario", "Bentancur", "Danso", "Richarlison", "Bissouma", "Cristian Romero",
    "Austin", "Muani", "Gallagher", "Kudus", "Spence", "Porro", "Udogie", "Pape Sarr",
    "Dragusin", "Simons", "Kinsky", "Tel", "Odobert", "Gray", "Bergvall", "Souza",
    "Ake", "Stones", "Bettinelli", "Ruben Dias", "Donnarumma", "Rodri", "Haaland",
    "Foden", "Marmoush", "Guehi", "Reijnders", "Semenyo", "Aït-Nouri", "Nunes",
    "N.González", "Trafford", "Cherki", "Doku", "Rico Lewis", "Savinho", "O'Reilly",
    "Khusanov", "Nypan", "Alleyne", "Clyne", "Benítez", "Hughes", "Lerma",
    "Dean Henderson", "Sosa", "Matthews", "Mateta", "Kamada", "Larsen", "Muñoz",
    "Lacroix", "Nketiah", "Doucouré", "Richards", "Guessand", "Pino", "Johnson",
    "Mitchell", "Riad", "Devenny", "Wharton", "Rodney", "Canvot", "Kporha", "Cardines",
    "Uche", "Doherty", "Bentley", "Johnstone", "Jose Sa", "Hwang", "Bueno", "Bellegarde",
    "Angel Gomes", "Krejci", "Wolfe", "Arokodare", "Tchatchoua", "Fraser", "González",
    "Lima", "Mané", "Darlow", "Cairns", "Byram", "Daniel James", "Calvert-Lewin",
    "Nmecha", "Perri", "Bornauw", "Justin", "Rodon", "Gudmundsson", "Ampadu", "Struijk",
    "Bogle", "Piroe", "Okafor", "Meslier", "Longstaff", "Tanaka", "Bijol", "Stach",
    "Gruev", "Aaronson", "Gnonto", "Buonanotte", "Crew", "Moore", "Xhaka", "Traore",
    "Alderete", "Reinildo", "O'Nien", "Mukiele", "Geertruida", "Isidor", "Le Fée",
    "Ballard", "Cirkin", "Brobbey", "Hume", "Mundle", "Ellborg", "Ba", "Diarra",
    "Mayenda", "Angulo", "Sadiki", "Jones", "Rigg", "Talbi", "Abdullahi", "Aleksic",
    "Bi", "Fabianski", "Callum Wilson", "Areola", "Soucek", "Bowen", "Disasi",
    "Walker-Peters", "Mavropanos", "Wan-Bissaka", "Castellanos", "Kilman", "Todibo",
    "Summerville", "Hermansen", "Pablo", "Potts", "Magassa", "Lamadrid",
    "Scarles", "Mayers", "Wood", "Sels", "Ortega", "Boly", "Gunn", "Aina", "Victor",
    "Awoniyi", "Sangare", "Anderson", "Milenkovic", "Gibbs-White", "Hudson-Odoi", "Yates",
    "Dominguez", "Lucca", "Ndoye", "Neco Williams", "Netz", "Bakwa", "Morato", "McAtee",
    "Savona", "Hutchinson", "Abbott", "Murillo", "Moreira", "Dubravka", "Walker",
    "Hladký", "Ward-Prowse", "Laurent", "Edwards", "Cullen", "Roberts", "Tuanzebe",
    "Tresor", "Worrall", "Ekdal", "Flemming", "Foster", "Beyer", "Hannibal", "Broja",
    "Estève", "Humphreys", "Amdouni", "Tchaouna", "Anthony", "Ugochukwu", "Pires",
    "Hartman", "Weiß", "Milner", "Steele", "Webster", "Welbeck", "Gross", "Veltman",
    "Dunk", "Boscagli", "Kadıoğlu", "Igor", "McGill", "O'Riley", "Mitoma",
    "Rutter", "De Cuyper", "Wieffer", "van Hecke", "Verbruggen", "Ayari", "Diego Gómez",
    "Baleba", "Tzimas", "Minteh", "Hinshelwood", "Kostoulas", "Forster", "Smith",
    "Christie", "E.Ünal", "Lewis Cook", "Brooks", "Adams", "Tavernier", "Senesi",
    "Petrovic", "Mandas", "Evanilson", "Hill", "Diakité", "Truffert", "Adli", "Scott",
    "Jimenez", "Doak", "Akinmboni", "Kroupi", "Soler", "Tóth", "Milosavljevic", "Rayan",
    "Ajer", "Henry", "Kelleher", "Dasilva", "Jensen", "Janelt", "Nelson", "Pinnock",
    "Balcombe", "Valdimarsson", "Damsgaard", "Carvalho", "Van den Berg", "Hickey",
    "Lewis-Potter", "Collins", "Schade", "Yarmolyuk", "Milambo", "Ouattara", "Kayode",
    "Furo", "Donovan", "Eyestone", "Matthäus", "Kompany",
    # 第二批补充
    "Van Dijk", "Chiesa", "Nyoni", "Leoni", "Ngumoha", "Guimaraes",
    "Bernardo Silva", "Gomes", "Diouf", "Kluivert",
    # 完整名字避免歧义
    "Bruno Fernandes", "Matheus Fernandes", "Solly March",
    # 补充缺失球员
    "Cambiaso", "Donyell Malen", "Malen", "Vinicius Junior", "Folarin Balogun",
    "Patrik Schick", "Lamine Yamal", "Rico Lewis",
]

# 按长度降序排列（确保"Inter Milan"比"Inter"先匹配）
STANDARD_NAMES_SORTED = sorted(STANDARD_NAMES, key=len, reverse=True)

def convert_beijing_to_utc(text):
    """将文章中所有北京时间（Beijing Time / CST / UTC+8）换算为 UTC"""
    import re
    from datetime import datetime, timedelta

    MONTHS = {
        'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
        'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
        'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,
        'sep':9,'oct':10,'nov':11,'dec':12,
    }
    BJ = r'(?:Beijing\s+[Tt]ime|CST|China\s+Standard\s+Time)'

    def day_sfx(d):
        return {1:'st',2:'nd',3:'rd'}.get(d%10 if d not in(11,12,13) else 0,'th')

    def bj_to_utc(hour, minute, ampm=''):
        if ampm.lower()=='pm' and hour!=12: hour+=12
        elif ampm.lower()=='am' and hour==12: hour=0
        return (datetime(2000,1,1,hour,minute)-timedelta(hours=8)).strftime('%H:%M')

    # 1. "Beijing time (CET+N) Month Day at H:MM [am/pm]"
    def _repl_prefix(m):
        mon=MONTHS.get(m.group(1).lower(),1); day=int(m.group(2))
        h=int(m.group(3)); mi=int(m.group(4) or 0); ap=m.group(5) or ''
        dt=(datetime(datetime.now().year,mon,day,h,mi)-timedelta(hours=8))
        if ap.lower()=='pm' and h!=12: dt-=timedelta(0)  # already handled below
        h2=h;
        if ap.lower()=='pm' and h2!=12: h2+=12
        elif ap.lower()=='am' and h2==12: h2=0
        dt=datetime(datetime.now().year,mon,day,h2,mi)-timedelta(hours=8)
        s=day_sfx(dt.day)
        return f"{dt.strftime('%B')} {dt.day}{s} at {dt.strftime('%H:%M')} UTC"

    text = re.sub(
        r'Beijing\s+[Tt]ime\s*\([^)]*\)\s*(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?',
        _repl_prefix, text, flags=re.IGNORECASE)

    # 2. "Month Day at H:MM [am/pm] [( ] Beijing Time/CST [ )]"
    def _repl_date(m):
        mon=MONTHS.get(m.group(1).lower(),1); day=int(m.group(2))
        h=int(m.group(3)); mi=int(m.group(4) or 0); ap=m.group(5) or ''
        if ap.lower()=='pm' and h!=12: h+=12
        elif ap.lower()=='am' and h==12: h=0
        dt=datetime(datetime.now().year,mon,day,h,mi)-timedelta(hours=8)
        s=day_sfx(dt.day)
        return f"{dt.strftime('%B')} {dt.day}{s} at {dt.strftime('%H:%M')} UTC"

    text = re.sub(
        r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+at\s+(\d{1,2}):(\d{2})\s*(am|pm)?\s*[\(\[]?\s*' + BJ + r'\s*[\)\]]?',
        _repl_date, text, flags=re.IGNORECASE)

    # 3. "H:MM [am/pm] [( ] Beijing Time/CST [ )]"
    text = re.sub(
        r'(\d{1,2}):(\d{2})\s*(am|pm)?\s*[\(\[]?\s*' + BJ + r'(?:\s*[\)\]])?',
        lambda m: bj_to_utc(int(m.group(1)),int(m.group(2)),m.group(3) or '')+' UTC',
        text, flags=re.IGNORECASE)

    # 4. "Hpm/Ham [( ] Beijing Time/CST [ )]"  (no colon)
    text = re.sub(
        r'(\d{1,2})\s*(am|pm)\s*[\(\[]?\s*' + BJ + r'(?:\s*[\)\]])?',
        lambda m: bj_to_utc(int(m.group(1)),0,m.group(2))+' UTC',
        text, flags=re.IGNORECASE)

    # 5. strip leftover labels
    text = re.sub(r'[\(\[]?\s*' + BJ + r'\s*[\)\]]?', '', text, flags=re.IGNORECASE)
    # fix any "UTCword" missing space
    text = re.sub(r'UTC(?=[a-zA-Z])', 'UTC ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def remove_beijing_time(text):
    """去掉文章里的 Beijing Time 表达"""
    # 匹配各种形式：Beijing Time, Beijing time, BeijingTime, beijing time
    patterns = [
        r'\s*Beijing\s*Time[,:\s]*',
        r'\s*\(Beijing\s*Time\)',
        r'\s*（Beijing\s*Time）',
    ]
    for p in patterns:
        text = re.sub(p, ' ', text, flags=re.IGNORECASE)
    # 清理多余空格
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def normalize_team_names(text):
    """将球队全称替换为简称"""
    for full, short in TEAM_NAME_MAP.items():
        text = re.sub(re.escape(full), short, text, flags=re.IGNORECASE)
    return text

def normalize_standard_names(text):
    """统一标准名字的大小写（遇到同名但大小写不同时，替换成标准形式）"""
    for name in STANDARD_NAMES_SORTED:
        pattern = r'\b' + re.escape(name) + r'\b'
        text = re.sub(pattern, name, text, flags=re.IGNORECASE)
    return text

def title_case(text):
    """英文标题 Title Case：除停用词外每个单词首字母大写"""
    stopwords = {"a", "an", "the", "and", "or", "but", "of", "in", "on", "at",
                 "to", "for", "with", "by", "from", "as", "vs", "nor", "yet", "so"}
    words = text.split()
    result = []
    for i, word in enumerate(words):
        # 第一个词和最后一个词始终大写
        if i == 0 or i == len(words) - 1:
            result.append(word[0].upper() + word[1:] if word else word)
        elif word.lower() in stopwords:
            result.append(word.lower())
        else:
            result.append(word[0].upper() + word[1:] if word else word)
    return ' '.join(result)


    """将球队全称替换为简称"""
    for full, short in TEAM_NAME_MAP.items():
        text = re.sub(re.escape(full), short, text, flags=re.IGNORECASE)
    return text

def capitalize_names_ai(text):
    """用 Claude 处理球队、球员、地名首字母大写"""
    if not text.strip():
        return text
    try:
        msg = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"Fix capitalization of proper nouns (team names, player names, place names, league names, competitions) in this English football headline. Do not change anything else. Return only the corrected headline, no explanation.\n\n{text}"
            }]
        )
        return msg.content[0].text.strip().strip('"').strip("'")
    except Exception as e:
        print(f"  [AI大写失败，使用规则处理] {e}")
        return text

def capitalize_names(text):
    """球队名首字母大写（规则 + AI）"""
    for team in TOP_TEAMS + list(TEAM_NAME_MAP.values()):
        pattern = r'\b' + re.escape(team.lower()) + r'\b'
        text = re.sub(pattern, team, text, flags=re.IGNORECASE)
    return text

def shorten_title(title):
    """标题超过100字符时缩短：在语义分隔符处截断"""
    if len(title) <= 100:
        return title
    # 按优先级找分隔符截断点
    for sep in [';', '–', '—', ':', ',']:
        idx = title.rfind(sep, 0, 100)
        if idx > 40:
            return title[:idx].strip()
    # 没有分隔符则在最后一个空格处截断
    truncated = title[:100]
    last_space = truncated.rfind(' ')
    return truncated[:last_space].strip() if last_space > 40 else truncated

def load_tag_overrides():
    path = "tag_overrides.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_team_players():
    path = "team_players.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

TAG_OVERRIDES = load_tag_overrides()
TEAM_PLAYERS = load_team_players()

def search_tag(name, context_teams=None):
    """搜索标签，返回 (value, relate_sd_id, label, remark)
    context_teams: 文章里出现的球队名列表，用于消歧重名
    """
    # 优先查覆盖映射
    if name in TAG_OVERRIDES:
        o = TAG_OVERRIDES[name]
        return o["value"], o["relate_sd_id"], o.get("label", ""), o.get("remark", "")

    for attempt in range(2):
        try:
            resp = session.get(
                "http://admin.allfootballapp.com/newarticle/admin/channel/search",
                params={"name": name, "language": "en"},
                timeout=10
            )
            break
        except Exception:
            if attempt == 1:
                return None
    results = resp.json().get("data", [])
    exclude_keywords = ["women", "female", "ladies", "reserve", "u21", "u23", "youth", "女", "预备", "青年"]
    filtered = [r for r in results if not any(kw in (r.get("label","")+r.get("remark","")+r.get("en_name","")).lower() for kw in exclude_keywords)]
    # 过滤掉组合标签（包含 / 或 or 的 en_name）
    filtered = [r for r in filtered if "/" not in r.get("en_name", "") and " or " not in r.get("en_name", "").lower()]

    if not filtered:
        return None

    # 多个结果时，优先选所属球队出现在文章里的
    # remark 字段是中文，需要英文→中文映射
    TEAM_CN = {
        "Arsenal": "阿森纳", "Chelsea": "切尔西", "Man United": "曼联",
        "Man City": "曼城", "Liverpool": "利物浦", "Tottenham": "热刺",
        "Newcastle": "纽卡斯尔", "Aston Villa": "阿斯顿维拉",
        "Real Madrid": "皇家马德里", "Barcelona": "巴塞罗那",
        "Atletico Madrid": "马德里竞技", "PSG": "巴黎圣日耳曼",
        "Bayern": "拜仁慕尼黑", "Dortmund": "多特蒙德",
        "Inter": "国际米兰", "Juventus": "尤文图斯",
        "Napoli": "那不勒斯", "Roma": "罗马", "Atalanta": "亚特兰大",
    }
    if len(filtered) > 1 and context_teams:
        for r in filtered:
            remark = r.get("remark", "").lower()
            for team in context_teams:
                cn = TEAM_CN.get(team, "")
                if team.lower() in remark or (cn and cn in remark):
                    return str(r["value"]), str(r["relate_sd_id"]), r.get("label", ""), r.get("remark", "")

    r = filtered[0]
    # 如果第一个结果的球队和文章上下文不匹配，尝试加破折号重搜
    if context_teams and " " in name:
        remark = r.get("remark", "").lower()
        match = any(
            team.lower() in remark or TEAM_CN.get(team, "") in remark
            for team in context_teams
        )
        if not match:
            dashed_name = name.replace(" ", "-")
            alt_resp = session.get(
                "http://admin.allfootballapp.com/newarticle/admin/channel/search",
                params={"name": dashed_name, "language": "en"}
            )
            alt_filtered = [x for x in alt_resp.json().get("data", [])
                           if not any(kw in (x.get("label","")+x.get("remark","")+x.get("en_name","")).lower()
                                     for kw in exclude_keywords)]
            for alt_r in alt_filtered:
                alt_remark = alt_r.get("remark", "").lower()
                if any(team.lower() in alt_remark or TEAM_CN.get(team, "") in alt_remark
                       for team in context_teams):
                    return str(alt_r["value"]), str(alt_r["relate_sd_id"]), alt_r.get("label", ""), alt_r.get("remark", "")

    return str(r["value"]), str(r["relate_sd_id"]), r.get("label", ""), r.get("remark", "")

def write_publish_log(article_id, title, tags, top_tag):
    """把发布详情写入日志文件，方便人工复查"""
    from datetime import datetime
    log_path = "publish_log.txt"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 文章 {article_id} ")
        f.write(f"{'[置顶池]' if top_tag == 'pool' else ''}\n")
        f.write(f"  标题: {title}\n")
        f.write(f"  标签 ({len(tags)}个):\n")
        for value, info in tags.items():
            f.write(f"    - {info['en_name']} → {info['label']} ({info['remark']}) [ID={value}]\n")

def extract_tags_from_content(title, body):
    """从标题和正文提取标签，返回 {value: {relate_sd_id, en_name, label, remark}}"""
    content = title + " " + body

    # 检测文章涉及哪些球队（去重）
    context_teams = list(dict.fromkeys(
        team for team in list(TEAM_NAME_MAP.values()) + TOP_TEAMS
        if re.search(r'\b' + re.escape(team) + r'\b', content, re.IGNORECASE)
    ))

    # 根据文章涉及的球队，建立"该球队球员优先"的名单
    priority_names = set()
    for team in context_teams:
        for players in TEAM_PLAYERS.get(team, []):
            priority_names.add(players.lower())

    found_names = []
    for name in STANDARD_NAMES_SORTED:
        pattern = r'\b' + re.escape(name) + r'\b'
        if re.search(pattern, content, re.IGNORECASE):
            found_names.append(name)

    tags = {}
    for name in found_names:
        is_priority = name.lower() in priority_names
        result = search_tag(name, context_teams=context_teams if is_priority else None)
        if result:
            value, relate_sd_id, label, remark = result
            tags[value] = {"relate_sd_id": relate_sd_id, "en_name": name, "label": label, "remark": remark}

    # 把文章里出现的球队名也加为标签
    for team in context_teams:
        result = search_tag(team)
        if result:
            value, relate_sd_id, label, remark = result
            if value not in tags:
                tags[value] = {"relate_sd_id": relate_sd_id, "en_name": team, "label": label, "remark": remark}

    # 转会逻辑：正文里出现转会关键词且涉及多个球队时，标记加 transfers 栏目
    transfer_keywords = [
        "transfer", "sign", "signing", "deal", "fee", "bid", "offer",
        "move", "join", "loan", "sell", "buy", "contract", "negotiate",
        "interested in", "target", "want to sign", "set to join"
    ]
    plain_body = re.sub('<[^>]+>', ' ', body).lower()
    has_transfer_keywords = any(kw in plain_body for kw in transfer_keywords)
    transfer_detected = has_transfer_keywords and len(context_teams) >= 2
    return tags, transfer_detected

def detect_world_cup_keywords(title, body):
    """关键词规则判断文章是否世界杯相关，返回 {is_wc, continents}"""
    content = (title + " " + body).lower()
    wc_keywords = ["world cup", "wc 2026", "2026 world cup", "fifa world cup", "world cup 2026",
                   "world cup squad", "world cup qualifier", "world cup final", "world cup group"]
    is_wc = any(kw in content for kw in wc_keywords)

    CONTINENT_COUNTRIES = {
        "Europe": ["portugal", "spain", "france", "germany", "england", "italy", "netherlands",
                   "belgium", "croatia", "denmark", "sweden", "switzerland", "austria", "poland",
                   "ukraine", "serbia", "hungary", "scotland", "wales", "czech", "slovakia",
                   "slovenia", "albania", "georgia", "turkey", "greece", "romania", "norway"],
        "Africa": ["morocco", "senegal", "nigeria", "egypt", "ivory coast", "cameroon", "ghana",
                   "tunisia", "algeria", "mali", "burkina faso", "guinea", "south africa",
                   "dr congo", "congo", "cape verde", "zambia", "tanzania", "mozambique"],
        "America": ["brazil", "argentina", "usa", "mexico", "colombia", "uruguay", "chile",
                    "ecuador", "peru", "venezuela", "paraguay", "bolivia", "canada",
                    "united states", "costa rica", "panama", "jamaica", "honduras"],
        "Asia": ["japan", "south korea", "iran", "saudi arabia", "australia", "china",
                 "qatar", "iraq", "uzbekistan", "jordan", "oman", "bahrain", "india",
                 "vietnam", "indonesia", "thailand", "philippines"],
    }
    continents = []
    for continent, countries in CONTINENT_COUNTRIES.items():
        if any(c in content for c in countries):
            if continent not in continents:
                continents.append(continent)

    # 国家队相关词也触发世界杯检测
    national_team_kw = ["national team", "fa president", "football federation", "football association",
                        "squad", "departure", "world cup squad", "fifa"]
    if not is_wc and any(kw in content for kw in national_team_kw) and continents:
        is_wc = True

    return {"is_wc": is_wc, "continents": continents}

# World Cup tab IDs
WC_TAB_IDS = {"WorldCup": "186", "AfFifaWC": "225", "Europe": "15", "Africa": "16", "America": "17", "Asia": "14"}
WC_CLASSIFICATION_ID = "164"  # 专题专栏: AF FIFA World Cup 2026

def involves_top_team(title, body):
    """判断文章是否涉及头部球队"""
    content = (title + " " + body).lower()
    for team in TOP_TEAMS:
        if team.lower() in content:
            return True
    return False

def process_article(article):
    """按规则处理文章：标题缩短、球队简称、首字母大写、判断置顶池"""
    title = article["title"]
    body = article["body"]

    # 去掉 Beijing Time，转换为 UTC
    body = convert_beijing_to_utc(body)
    title = convert_beijing_to_utc(title)

    # 规则2：球队全称转简称
    title = normalize_team_names(title)
    body = normalize_team_names(body)

    # 标题里 Champions League → UCL（正文保持不变）
    title = re.sub(r'\bChampions League\b', 'UCL', title, flags=re.IGNORECASE)

    # 规则3：标准名字大小写统一
    title = normalize_standard_names(title)
    body = normalize_standard_names(body)

    # 规则1：标题超过100字符则缩短
    if len(title) > 100:
        title = shorten_title(title)
        title = normalize_team_names(title)
        title = normalize_standard_names(title)

    # 规则3补充：已知球队简称大小写统一（覆盖 TOP_TEAMS）
    title = capitalize_names(title)

    # Title Case：标题所有实词首字母大写
    title = title_case(title)

    # 规则4：涉及头部球队则进入置顶池
    top_tag = "pool" if involves_top_team(title, body) else "nil"

    # 提取标签
    tags, transfer_detected = extract_tags_from_content(title, body)

    article["title"] = title
    article["body"] = body
    article["top_tag"] = top_tag
    article["tags"] = tags
    article["transfer_detected"] = transfer_detected

    # 世界杯检测：追加专栏
    wc = detect_world_cup_keywords(title, body)
    if wc["is_wc"]:
        current_tabs = [str(t) for t in article.get("original_tabs", [])]
        extra = [WC_TAB_IDS["WorldCup"], WC_TAB_IDS["AfFifaWC"]]
        for cont in wc["continents"]:
            if WC_TAB_IDS.get(cont):
                extra.append(WC_TAB_IDS[cont])
        for t in extra:
            if t and t not in current_tabs:
                current_tabs.append(t)
        article["original_tabs"] = current_tabs

    # 有 World Cup 专栏的文章强制加 AF FIFA WC 2026 专题专栏并进置顶池
    final_tabs = [str(t) for t in article.get("original_tabs", [])]
    if WC_TAB_IDS["WorldCup"] in final_tabs:
        if WC_TAB_IDS["AfFifaWC"] not in final_tabs:
            final_tabs.append(WC_TAB_IDS["AfFifaWC"])
            article["original_tabs"] = final_tabs
        article["top_tag"] = "pool"
        article["classifications"] = [WC_CLASSIFICATION_ID]

    return article


def get_drafts(limit=10):
    """获取草稿列表"""
    resp = session.get(
        "http://admin.allfootballapp.com/newarticle/admin/archives/list",
        params={"language": "en", "tab_type": "archive_status", "tab": "0", "page": 1, "per_page": limit}
    )
    return resp.json()["data"]["archives"]

def get_article_detail(article_id):
    """获取文章详情（包含正文和原有 tabs）"""
    resp = session.get(
        "http://admin.allfootballapp.com/newarticle/admin/archives/view",
        params={"type": "article", "id": article_id, "language": "en", "include_body": "1"}
    )
    archive = resp.json()["data"]["archive"]
    archive["body"] = archive.get("ext", {}).get("archive_body", "")
    # 保存原有专栏 tabs（不是球队标签）
    archive["original_tabs"] = archive.get("ext", {}).get("archive_tabs", {}).get("common", [])
    return archive

def publish_article(article_id, article_data):
    """发布文章"""
    post_data = {
        "status": "1",
        "type": "article",
        "title": article_data["title"],
        "source": article_data.get("source", ""),
        "source_url": article_data.get("source_url", ""),
        "writer": article_data.get("writer", ""),
        "litpic": article_data.get("litpic", ""),
        "display_time": article_data.get("display_time", ""),
        "sort_time": article_data.get("sort_time", ""),
        "language": "en",
        "add_to_tab": "1",
        "antispam_status": "1",
        "style": article_data.get("style", "default"),
        "redirect_in_app": "0",
        "tab_recommend": "1",
        "body": article_data.get("body", ""),
        "con": article_data.get("body", ""),
        "top_tag": article_data.get("top_tag", "nil"),
        "from_third_part": "0",
        "insert_comment": "0",
    }

    # channels：只传新提取的标签
    tags = article_data.get("tags", {})
    new_channels = list(tags.keys()) if tags else ["264"]

    # 明确传空的 object_attr 字段，防止服务器保留旧标签
    post_data["object_attr_channel"] = ""
    post_data["object_attr_other"] = ""
    post_data["event_attr"] = ""

    for i, ch in enumerate(new_channels):
        post_data[f"channels[{i}]"] = ch
        post_data[f"channels_level[{ch}]"] = "A"

    print(f"  发布channels: {new_channels}")

    # 保留原有专栏 tabs，转会文章加入 Transfers(id=2)
    original_tabs = article_data.get("original_tabs", [])
    tabs = [str(t) for t in original_tabs] if original_tabs else ["1", "4"]
    if article_data.get("transfer_detected") and "2" not in tabs:
        tabs.append("2")
    for i, t in enumerate(tabs):
        post_data[f"tabs[{i}]"] = t

    for i, c in enumerate(article_data.get("classifications", [])):
        post_data[f"classifications[{i}]"] = c

    for attempt in range(2):
        try:
            resp = session.post(
                f"http://admin.allfootballapp.com/newarticle/admin/archives/edit?id={article_id}",
                data=post_data,
                timeout=30
            )
            return resp.json()
        except Exception as e:
            if attempt == 1:
                raise

if __name__ == "__main__":
    import sys

    # 支持指定序号：python auto_publish.py 2,5,6 或 python auto_publish.py 3
    arg = sys.argv[1].replace("，", ",") if len(sys.argv) > 1 else "n20"

    print("=== 获取草稿列表（来源：DongQiuDi）===")
    all_drafts = get_drafts(limit=100)
    drafts_pool = [d for d in all_drafts if d.get("source", "").lower() == "dongqiudi"]

    if not drafts_pool:
        print("没有来自 DongQiuDi 的草稿")
        exit()

    # 显示列表
    for i, d in enumerate(drafts_pool[:20]):
        print(f"{i+1}. [{d['id']}] {d['title'][:70]}")

    # 解析参数
    first = arg.split(",")[0].strip()
    if "," in arg and len(first) >= 7 and first.isdigit():
        # 逗号分隔的文章ID：4471361,4471366
        ids = [x.strip() for x in arg.split(",")]
        drafts = [d for d in drafts_pool if d["id"] in ids]
    elif len(arg) >= 7 and arg.isdigit():
        # 单个文章ID：4471361
        drafts = [d for d in drafts_pool if d["id"] == arg]
        if not drafts:
            print(f"草稿列表里找不到文章 {arg}")
            exit()
    elif "," in arg:
        # 逗号分隔的序号：1,2,4,5,8
        indices = [int(x.strip()) - 1 for x in arg.split(",")]
        drafts = [drafts_pool[i] for i in indices if 0 <= i < len(drafts_pool)]
    elif arg.startswith("n"):
        # n10 → 发前10篇
        drafts = drafts_pool[:int(arg[1:])]
    else:
        # 单个序号：3 → 只发第3篇
        idx = int(arg) - 1
        drafts = [drafts_pool[idx]] if 0 <= idx < len(drafts_pool) else []

    print(f"\n将发布 {len(drafts)} 篇：{[d['id'] for d in drafts]}")
    confirm = input("确认按规则改稿并发布？(yes/no/输入新的文章ID或序号): ").strip()

    if confirm.lower() == "no" or confirm == "":
        print("已取消")
        exit()
    elif confirm.lower() != "yes":
        # 重新解析输入的 ID 或序号
        new_arg = confirm.replace("，", ",")
        first = new_arg.split(",")[0].strip()
        if len(first) >= 7 and first.isdigit():
            ids = [x.strip() for x in new_arg.split(",")]
            drafts = [d for d in drafts_pool if d["id"] in ids]
        elif "," in new_arg:
            indices = [int(x.strip()) - 1 for x in new_arg.split(",")]
            drafts = [drafts_pool[i] for i in indices if 0 <= i < len(drafts_pool)]
        else:
            idx = int(new_arg) - 1
            drafts = [drafts_pool[idx]] if 0 <= idx < len(drafts_pool) else []
        print(f"重新选择：将发布 {len(drafts)} 篇：{[d['id'] for d in drafts]}")
        if not drafts:
            print("未找到对应文章")
            exit()

    print("\n=== 开始批量改稿 + 发布 ===")
    for d in drafts:
        try:
            article = get_article_detail(d["id"])
            original_title = article["title"]
            article = process_article(article)

            title_changed = "(标题已改)" if article["title"] != original_title else ""
            pool_tag = "[置顶池]" if article["top_tag"] == "pool" else ""

            result = publish_article(d["id"], article)
            status = "成功" if result.get("errno") == 0 else f"失败: {result.get('errmsg')}"
            print(f"[{d['id']}] {status} {pool_tag} {title_changed} - {article['title'][:60]}")

            # 记录发布日志
            if result.get("errno") == 0:
                write_publish_log(d["id"], article["title"], article.get("tags", {}), article.get("top_tag", "nil"))
        except Exception as e:
            print(f"[{d['id']}] 错误: {e}")
            import traceback
            traceback.print_exc()
