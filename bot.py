import os
import logging
import psycopg2
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do logger para registrar erros locais
logging.basicConfig(
    level=logging.ERROR,
    filename="bot_errors.log",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Configuração dos canais
try:
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CANAL_PUBLICO = os.getenv("CANAL_PUBLICO")
    DATABASE_URL = os.getenv("DATABASE_URL")

    if not all([API_ID, API_HASH, BOT_TOKEN, CANAL_PUBLICO, DATABASE_URL]):
        raise ValueError("Certifique-se de que todas as variáveis de ambiente estão configuradas no arquivo .env.")
    if not CANAL_PUBLICO.startswith("@"):
        raise ValueError("O valor de CANAL_PUBLICO deve começar com '@'.")
except Exception as e:
    raise SystemExit(f"Erro na configuração do bot: {e}")

# Inicialização do bot
bot = Client(
    "anon_messages_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Variável global para controlar o estado do bot
bot_status = False  # True para ativo, False para inativo

# Seu ID de usuário como dono do bot
OWNER_ID = 737737727  # Substitua pelo seu ID

# Conexão com o banco de dados PostgreSQL
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL UNIQUE,
            is_admin BOOLEAN DEFAULT FALSE
        );
    """)
    # --- Tabela de bloqueio ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id BIGINT PRIMARY KEY
        );
    """)
    conn.commit()
except Exception as e:
    raise SystemExit(f"Erro ao conectar ao banco de dados: {e}")

# Função para verificar se um usuário é administrador
def is_admin(user_id):
    try:
        if user_id == OWNER_ID:
            return True
        cursor.execute("SELECT is_admin FROM users WHERE user_id = %s;", (user_id,))
        result = cursor.fetchone()
        return result is not None and result[0]
    except Exception as e:
        logging.error(f"Erro ao verificar administrador: {e}")
        return False

# Funções de bloqueio de usuário
def block_user_db(user_id):
    try:
        cursor.execute("INSERT INTO blocked_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING;", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Erro ao bloquear usuário: {e}")
        return False

def unblock_user_db(user_id):
    try:
        cursor.execute("DELETE FROM blocked_users WHERE user_id = %s;", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Erro ao desbloquear usuário: {e}")
        return False

def is_user_blocked(user_id):
    try:
        cursor.execute("SELECT 1 FROM blocked_users WHERE user_id = %s;", (user_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logging.error(f"Erro ao verificar bloqueio de usuário: {e}")
        return False

# Comando /block
@bot.on_message(filters.command("block"))
async def block_cmd(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("Use: /block <user_id>")
            return
        target_id = int(parts[1])
        if block_user_db(target_id):
            await message.reply(f"Usuário {target_id} bloqueado com sucesso!")
            # log removido
        else:
            await message.reply("Erro ao bloquear usuário.")
    except Exception as e:
        await message.reply("Erro ao processar comando. Use: /block <user_id>")

# Comando /desblock
@bot.on_message(filters.command("desblock"))
async def unblock_cmd(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("Use: /desblock <user_id>")
            return
        target_id = int(parts[1])
        if unblock_user_db(target_id):
            await message.reply(f"Usuário {target_id} desbloqueado com sucesso!")
            # log removido
        else:
            await message.reply("Erro ao desbloquear usuário.")
    except Exception as e:
        await message.reply("Erro ao processar comando. Use: /desblock <user_id>")

# Comando /on - Ativar o bot
@bot.on_message(filters.command("on"))
async def activate_bot(client, message):
    global bot_status
    if is_admin(message.from_user.id):
        bot_status = True
        await message.reply("✅ O bot foi ativado para todos os usuários.")
        # log removido
        try:
            await client.send_message(
                chat_id=CANAL_PUBLICO,
                text="✅ **O bot está agora ativo!**\n\nEnvie suas mensagens anônimas diretamente para este canal."
            )
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem de ativação para o canal: {e}")
    else:
        await message.reply("⛔ Você não tem permissão para usar este comando.")

# Comando /off - Desativar o bot
@bot.on_message(filters.command("off"))
async def deactivate_bot(client, message):
    global bot_status
    if is_admin(message.from_user.id):
        bot_status = False
        await message.reply(
            "⛔ O bot foi desativado para todos os usuários.\n\n"
            "Por favor, aguarde o aviso no canal para saber quando ele estará disponível novamente.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 Acompanhe no canal", url=f"https://t.me/{CANAL_PUBLICO[1:]}")]]
            )
        )
        # log removido
        try:
            await client.send_message(
                chat_id=CANAL_PUBLICO,
                text="⛔ **O bot foi desativado.**\n\nPor favor, aguarde para novas atualizações."
            )
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem de desativação para o canal: {e}")
    else:
        await message.reply("⛔ Você não tem permissão para usar este comando.")

# Comando /start
@bot.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or ""
    user_username = message.from_user.username or ""
    try:
        cursor.execute(
            "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING;",
            (user_id,)
        )
        conn.commit()
        # log removido
        buttons = [
            [InlineKeyboardButton("ℹ️ Como usar", callback_data="help")],
            [
                InlineKeyboardButton("👨‍💻 Criador", url="https://t.me/mulheres_apaixonadas"),
                InlineKeyboardButton("🛠️ Dev", url="https://t.me/lndescritivel")
            ]
        ]
        await message.reply(
            "🤖 Olá! Bem-vindo ao bot de mensagens anônimas!\n"
            "Envie qualquer mensagem aqui e ela será enviada anonimamente para o canal.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logging.error(f"Erro ao registrar usuário no banco de dados: {e}")
        await message.reply("❌ Ocorreu um erro ao registrar seu acesso. Tente novamente mais tarde.")

# Comando para exportar usuários em .txt (apenas admin)
@bot.on_message(filters.command("export_users"))
async def export_users(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return

    try:
        cursor.execute("SELECT user_id FROM users;")
        users = cursor.fetchall()
        users_info = []
        for (user_id,) in users:
            try:
                user = await client.get_users(user_id)
                name = user.first_name or ""
                username = user.username or ""
                users_info.append(f"{name} (@{username}) - ID: {user_id}")
            except Exception:
                users_info.append(f"ID: {user_id} (não foi possível obter o nome)")
        with open("usuarios.txt", "w", encoding="utf-8") as f:
            for line in users_info:
                f.write(line + "\n")
        await message.reply_document("usuarios.txt", caption="Lista de usuários do bot:")
        # log removido
    except Exception as e:
        logging.error(f"Erro ao exportar usuários: {e}")
        await message.reply("❌ Ocorreu um erro ao exportar os usuários.")

# Callback dos botões
@bot.on_callback_query()
async def callback_query_handler(client, callback_query):
    if callback_query.data == "help":
        await callback_query.message.edit(
            "ℹ️ **Como usar o bot de mensagens anônimas:**\n\n"
            "1. Escreva sua mensagem diretamente no chat com o bot.\n"
            "2. O bot enviará sua mensagem anonimamente para o canal.\n\n"
            "🛸 **zoeira autorizada!**\n\n"
            "🎭 Entre no clima da provocação divertida com estilo e criatividade. Aqui, as farpas voam como discos voadores — mas sempre com respeito.\n\n"
            "⚠️ Sem ofensas pessoais, sem baixaria. Brinque, provoque, mas lembre-se: até os ETs têm limite! 👽"
        )

# Recebendo mensagens do usuário
@bot.on_message(filters.private & ~filters.command(["start", "help", "on", "off", "add_admin", "export_users", "block", "desblock"]))
async def handle_anonymous_message(client, message):
    global bot_status
    user_id = message.from_user.id

    # --- Checagem de bloqueio ---
    if is_user_blocked(user_id):
        await message.reply("⛔ Você está bloqueado(a) e não pode usar o bot.")
        return

    if not bot_status:
        await message.reply(
            "⚠️ O bot está indisponível no momento.\n"
            "Por favor, aguarde o aviso no canal para saber quando ele estará disponível novamente.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 Acompanhe no canal", url=f"https://t.me/{CANAL_PUBLICO[1:]}")]]
            )
        )
        return

    if message.text:
        try:
            user_name = message.from_user.first_name or ""
            user_username = message.from_user.username or ""
            # log removido
            await client.send_message(
                chat_id=CANAL_PUBLICO,
                text=f"📢 **Nova mensagem anônima:**\n\n{message.text}"
            )
            await message.reply("✅ Sua mensagem anônima foi enviada com sucesso no canal!")
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem: {e}")
            await message.reply(
                "❌ Ocorreu um erro ao enviar sua mensagem. Por favor, tente novamente mais tarde ou verifique as configurações do bot."
            )
    else:
        await message.reply("❌ Apenas mensagens de texto são suportadas no momento.")

# Comando /add_admin
@bot.on_message(filters.command("add_admin"))
async def add_admin_cmd(client, message):
    # Só o OWNER pode adicionar novos admins
    if message.from_user.id != OWNER_ID:
        await message.reply("⛔ Apenas o proprietário pode adicionar novos administradores.")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("Use: /add_admin <user_id>")
            return
        target_id = int(parts[1])
        cursor.execute("INSERT INTO users (user_id, is_admin) VALUES (%s, TRUE) ON CONFLICT (user_id) DO UPDATE SET is_admin = TRUE;", (target_id,))
        conn.commit()
        await message.reply(f"✅ Usuário {target_id} agora é administrador.")
        # log removido
    except Exception as e:
        logging.error(f"Erro ao adicionar admin: {e}")
        await message.reply("❌ Erro ao adicionar admin. Use: /add_admin <user_id>")

# Comando /remove_admin
@bot.on_message(filters.command("remove_admin"))
async def remove_admin_cmd(client, message):
    # Só o OWNER pode remover administradores
    if message.from_user.id != OWNER_ID:
        await message.reply("⛔ Apenas o proprietário pode remover administradores.")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("Use: /remove_admin <user_id>")
            return
        target_id = int(parts[1])
        cursor.execute(
            "UPDATE users SET is_admin = FALSE WHERE user_id = %s;",
            (target_id,)
        )
        conn.commit()
        await message.reply(f"✅ Usuário {target_id} não é mais administrador.")
        # log removido
    except Exception as e:
        logging.error(f"Erro ao remover admin: {e}")
        await message.reply("❌ Erro ao remover admin. Use: /remove_admin <user_id>")

# Comando /list_admins
@bot.on_message(filters.command("list_admins"))
async def list_admins_cmd(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ Você não tem permissão para usar este comando.")
        return

    try:
        cursor.execute("SELECT user_id FROM users WHERE is_admin = TRUE;")
        admins = cursor.fetchall()
        if not admins:
            await message.reply("Nenhum administrador encontrado.")
            return

        admin_infos = []
        for (admin_id,) in admins:
            try:
                user = await client.get_users(admin_id)
                name = user.first_name or ""
                username = f"@{user.username}" if user.username else ""
                admin_infos.append(f"{name} {username} - ID: {admin_id}")
            except Exception:
                admin_infos.append(f"ID: {admin_id} (não foi possível obter o nome)")

        response = "👑 **Administradores:**\n\n" + "\n".join(admin_infos)
        await message.reply(response)
    except Exception as e:
        logging.error(f"Erro ao listar admins: {e}")
        await message.reply("❌ Erro ao listar administradores.")
        
if __name__ == "__main__":
    print("Bot iniciado...")
    bot.run()
