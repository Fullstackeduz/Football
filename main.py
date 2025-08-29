import random, time, threading
import sqlite3
from telebot import TeleBot, types

bot = TeleBot("8211115694:AAEt6fIAIK1BoBwiymNiyekIn0AmIbpr574")  # TOKEN o‘rniga bot tokeningiz

# --- BAZA ---
conn = sqlite3.connect("league.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS league_sessions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS league_players(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id INTEGER,
    user_id INTEGER,
    username TEXT,
    points INTEGER DEFAULT 0,
    goals_scored INTEGER DEFAULT 0,
    goals_conceded INTEGER DEFAULT 0,
    credits INTEGER DEFAULT 100,
    kit TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS players_squad(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id INTEGER,
    user_id INTEGER,
    name TEXT,
    position TEXT,
    rating INTEGER
)
""")
conn.commit()

POSITIONS = ["GK", "DF", "MF", "FW"]
NAMES = ["Messi","Ronaldo","Mbappe","Haaland","Bellingham","Modric","Kroos",
         "Neymar","Vinicius","Lewandowski","Salah","De Bruyne","Son","Odegaard","Casemiro"]

# --- Bozor ---
def generate_market():
    return [(random.choice(NAMES), random.choice(POSITIONS), random.randint(70,99), random.randint(20,50)) for _ in range(3)]

@bot.message_handler(commands=["market"])
def open_market(message):
    chat_id = message.chat.id
    cursor.execute("SELECT id FROM league_sessions WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    if not row:
        bot.send_message(chat_id, "❌ Avval /league orqali liga oching!")
        return
    league_id = row[0]
    players = generate_market()
    markup = types.InlineKeyboardMarkup()
    for (name, pos, rating, price) in players:
        markup.add(types.InlineKeyboardButton(
            f"⚽ {name} ({pos}, {rating}) – {price}💰",
            callback_data=f"buy:{league_id}:{message.from_user.id}:{name}:{pos}:{rating}:{price}"
        ))
    bot.send_message(chat_id, "🛒 Transfer bozori:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy:"))
def buy_player(call):
    _, league_id, uid, name, pos, rating, price = call.data.split(":")
    league_id, uid, rating, price = int(league_id), int(uid), int(rating), int(price)
    cursor.execute("SELECT credits FROM league_players WHERE league_id=? AND user_id=?", (league_id, uid))
    row = cursor.fetchone()
    if not row:
        bot.answer_callback_query(call.id, "❌ Siz ligaga qo‘shilmagansiz.")
        return
    credits = row[0]
    if credits < price:
        bot.answer_callback_query(call.id, "💸 Pul yetarli emas!")
        return
    cursor.execute("INSERT INTO players_squad(league_id, user_id, name, position, rating) VALUES(?,?,?,?,?)",
                   (league_id, uid, name, pos, rating))
    cursor.execute("UPDATE league_players SET credits = credits - ? WHERE league_id=? AND user_id=?",
                   (price, league_id, uid))
    conn.commit()
    bot.answer_callback_query(call.id, f"✅ {name} ({pos}, {rating}) jamoangizga qo‘shildi!")

# --- Forma ---
@bot.message_handler(commands=["kit"])
def choose_kit(message):
    chat_id = message.chat.id
    cursor.execute("SELECT id FROM league_sessions WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    if not row:
        bot.send_message(chat_id, "❌ Avval /league orqali liga oching!")
        return
    league_id = row[0]
    markup = types.InlineKeyboardMarkup()
    for color in ["🔴 Qizil","🔵 Ko‘k","🟢 Yashil","⚪ Oq"]:
        markup.add(types.InlineKeyboardButton(color,
            callback_data=f"kit:{league_id}:{message.from_user.id}:{color}"))
    bot.send_message(chat_id,"👕 Formani tanlang:",reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("kit:"))
def set_kit(call):
    _, league_id, uid, color = call.data.split(":")
    cursor.execute("UPDATE league_players SET kit=? WHERE league_id=? AND user_id=?", (color,int(league_id),int(uid)))
    conn.commit()
    bot.answer_callback_query(call.id,f"✅ Sizning formaniz: {color}")

# --- Squad media card ---
@bot.message_handler(commands=["squad"])
def show_squad(message):
    chat_id = message.chat.id
    cursor.execute("SELECT id FROM league_sessions WHERE chat_id=?",(chat_id,))
    row = cursor.fetchone()
    if not row: bot.send_message(chat_id,"❌ Avval /league orqali liga oching!"); return
    league_id = row[0]; uid = message.from_user.id
    cursor.execute("SELECT credits, kit FROM league_players WHERE league_id=? AND user_id=?",(league_id,uid))
    pl = cursor.fetchone()
    if not pl: bot.send_message(chat_id,"❌ Siz ligada emassiz."); return
    credits, kit = pl
    cursor.execute("SELECT name, position, rating FROM players_squad WHERE league_id=? AND user_id=?",(league_id,uid))
    players = cursor.fetchall()
    text=f"👤 {message.from_user.first_name}\n💰 Balans: {credits}\n👕 Forma: {kit if kit else 'Tanlanmagan'}\n\n"
    if players: text+="📋 Jamoangiz:\n"+"\n".join([f" - {name} ({pos}, {rating})" for name,pos,rating in players])
    else: text+="❌ Siz hali futbolchi sotib olmadingiz."
    # Inline media card style
    markup=types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data=f"squad_refresh:{league_id}:{uid}"))
    bot.send_message(chat_id,text,reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("squad_refresh"))
def refresh_squad(call):
    _, league_id, uid = call.data.split(":")
    uid=int(uid)
    cursor.execute("SELECT credits, kit FROM league_players WHERE league_id=? AND user_id=?",(league_id,uid))
    credits, kit = cursor.fetchone()
    cursor.execute("SELECT name, position, rating FROM players_squad WHERE league_id=? AND user_id=?",(league_id,uid))
    players=cursor.fetchall()
    text=f"👤 {call.from_user.first_name}\n💰 Balans: {credits}\n👕 Forma: {kit if kit else 'Tanlanmagan'}\n\n"
    if players: text+="📋 Jamoangiz:\n"+"\n".join([f" - {name} ({pos}, {rating})" for name,pos,rating in players])
    else: text+="❌ Siz hali futbolchi sotib olmadingiz."
    bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.message_id,text=text)

# --- Liga ---
@bot.message_handler(commands=["league"])
def league_menu(message):
    chat_id=message.chat.id
    cursor.execute("SELECT id FROM league_sessions WHERE chat_id=?",(chat_id,))
    row=cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO league_sessions(chat_id) VALUES(?)",(chat_id,))
        conn.commit()
    markup=types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Ligaga qo‘shilish",callback_data=f"l_join:{chat_id}"))
    markup.add(types.InlineKeyboardButton("▶ Ligani boshlash",callback_data=f"l_start:{chat_id}"))
    bot.send_message(chat_id,"⚽ Liga menyusi:",reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("l_join"))
def join_league(call):
    chat_id=int(call.data.split(":")[1])
    uid=call.from_user.id; username=call.from_user.first_name
    cursor.execute("SELECT id FROM league_sessions WHERE chat_id=?",(chat_id,))
    league_id=cursor.fetchone()[0]
    cursor.execute("SELECT * FROM league_players WHERE league_id=? AND user_id=?",(league_id,uid))
    if cursor.fetchone(): bot.answer_callback_query(call.id,"❌ Siz allaqachon ligadasiz.")
    else:
        cursor.execute("INSERT INTO league_players(league_id,user_id,username) VALUES(?,?,?)",(league_id,uid,username))
        conn.commit()
        bot.answer_callback_query(call.id,"✅ Ligaga qo‘shildingiz!")

# --- Match engine with inline dashboard ---
def calc_goal_prob(rating_off,rating_def): return max(0.05,min(0.6,0.1+(rating_off-rating_def)/300))

def simulate_match(chat_id,league_id,p1,p2):
    cursor.execute("SELECT username FROM league_players WHERE league_id=? AND user_id=?",(league_id,p1))
    name1=cursor.fetchone()[0]
    cursor.execute("SELECT username FROM league_players WHERE league_id=? AND user_id=?",(league_id,p2))
    name2=cursor.fetchone()[0]
    score1,score2=0,0
    cursor.execute("SELECT SUM(rating) FROM players_squad WHERE league_id=? AND user_id=?",(league_id,p1))
    rating1=cursor.fetchone()[0] or 70
    cursor.execute("SELECT SUM(rating) FROM players_squad WHERE league_id=? AND user_id=?",(league_id,p2))
    rating2=cursor.fetchone()[0] or 70
    msg=bot.send_message(chat_id,f"⚽ {name1} vs {name2}\n⏱ 0\' Hisob: 0:0")
    for minute in range(1,3):
        time.sleep(30)
        events=[]
        g1=sum([1 for _ in range(random.randint(0,3)) if random.random()<calc_goal_prob(rating1,rating2)])
        g2=sum([1 for _ in range(random.randint(0,3)) if random.random()<calc_goal_prob(rating2,rating1)])
        score1+=g1; score2+=g2
        if g1>0: events.append(f"⚽ {name1} {g1} gol urdi!")
        if g2>0: events.append(f"⚽ {name2} {g2} gol urdi!")
        if random.random()<0.2: events.append(f"🟨 {name1} sariq kartochka oldi!")
        if random.random()<0.2: events.append(f"🟨 {name2} sariq kartochka oldi!")
        progress="█"*minute+"░"*(2-minute)
        text=f"⚽ {name1} vs {name2}\n⏱ {minute*45}\' Hisob: {score1}:{score2}\n{progress}\n"+"\n".join(events)
        bot.edit_message_text(chat_id=chat_id,message_id=msg.message_id,text=text)
    bot.send_message(chat_id,f"🔔 O‘yin tugadi! Natija: {name1} {score1} - {score2} {name2}")
    if score1>score2: cursor.execute("UPDATE league_players SET points=points+3 WHERE league_id=? AND user_id=?",(league_id,p1))
    elif score2>score1: cursor.execute("UPDATE league_players SET points=points+3 WHERE league_id=? AND user_id=?",(league_id,p2))
    else: cursor.execute("UPDATE league_players SET points=points+1 WHERE league_id=? AND user_id IN (?,?)",(league_id,p1,p2))
    cursor.execute("UPDATE league_players SET goals_scored=goals_scored+?,goals_conceded=goals_conceded+? WHERE league_id=? AND user_id=?",(score1,score2,league_id,p1))
    cursor.execute("UPDATE league_players SET goals_scored=goals_scored+?,goals_conceded=goals_conceded+? WHERE league_id=? AND user_id=?",(score2,score1,league_id,p2))
    conn.commit()

@bot.callback_query_handler(func=lambda call: call.data.startswith("l_start"))
def start_league(call):
    chat_id=int(call.data.split(":")[1])
    cursor.execute("SELECT id FROM league_sessions WHERE chat_id=?",(chat_id,))
    league_id=cursor.fetchone()[0]
    cursor.execute("SELECT user_id FROM league_players WHERE league_id=?",(league_id,))
    players=[row[0] for row in cursor.fetchall()]
    if len(players)<2: bot.answer_callback_query(call.id,"❌ Liga uchun kamida 2 ta o‘yinchi kerak."); return
    bot.answer_callback_query(call.id,"▶ Liga boshlandi!")
    bot.send_message(chat_id,"⚔ PvP o‘yinlar start oldi!")

    threads=[]
    for i in range(len(players)):
        for j in range(i+1,len(players)):
            t=threading.Thread(target=simulate_match,args=(chat_id,league_id,players[i],players[j]))
            t.start(); threads.append(t)
    for t in threads: t.join()

    # Yakuniy jadval va MVP
    cursor.execute("SELECT username, points, goals_scored, goals_conceded FROM league_players WHERE league_id=? ORDER BY points DESC, goals_scored DESC",(league_id,))
    rows=cursor.fetchall()
    text="🏆 Liga Yakuniy Jadvali:\n\n"
    for idx,(username,pts,gs,gc) in enumerate(rows,1):
        text+=f"{idx}. {username} — {pts} ochko (G:{gs}/O:{gc})\n"
    bot.send_message(chat_id,text)

    cursor.execute("SELECT username, MAX(goals_scored) FROM league_players WHERE league_id=?",(league_id,))
    mvp=cursor.fetchone()
    bot.send_message(chat_id,f"🏅 Eng yaxshi golchi: {mvp[0]} — {mvp[1]} gol")

    cursor.execute("DELETE FROM league_players WHERE league_id=?",(league_id,))
    cursor.execute("DELETE FROM players_squad WHERE league_id=?",(league_id,))
    cursor.execute("DELETE FROM league_sessions WHERE id=?",(league_id,))
    conn.commit()

bot.polling(none_stop)