"""Welcome messages, reaction roles, polls, suggestions and reports."""

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import channel_link, find_channel, mod_log

REPORT_SENT = "✅ Thanks. Staff have been notified privately."
REPORT_FAILED = ("⚠️ I could not deliver your report because this server has no #mod-log channel. "
                 "Please message a staff member directly.")

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class ReportModal(discord.ui.Modal, title="Report this message to staff"):
    reason = discord.ui.TextInput(label="What's wrong with it?", style=discord.TextStyle.paragraph,
                                  max_length=500, placeholder="e.g. harassment, scam link, spam")

    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message

    async def on_submit(self, interaction: discord.Interaction):
        m = self.message
        delivered = await mod_log(interaction.guild, "🚩 Message reported",
                      f"**Reported by:** {interaction.user.mention}\n"
                      f"**Author:** {m.author.mention} (`{m.author.id}`)\n"
                      f"**Message:** [jump to message]({m.jump_url})\n"
                      f"> {m.content[:700] or '*(attachment only)*'}\n"
                      f"**Reason:** {self.reason.value}",
                      color=config.COLOR_BAD, important=True)
        await interaction.response.send_message(
            REPORT_SENT if delivered else REPORT_FAILED, ephemeral=True)


class Community(commands.Cog):
    """Polls, suggestions, reports and member onboarding."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Right-click a message → Apps → "Report to staff"
        self.report_menu = app_commands.ContextMenu(name="Report to staff", callback=self.report_message)
        self.bot.tree.add_command(self.report_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.report_menu.name, type=self.report_menu.type)

    # --- Welcome --------------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        g = member.guild
        role = discord.utils.get(g.roles, name=config.MEMBER_ROLE)
        if role:
            try:
                await member.add_roles(role, reason="New member")
            except discord.HTTPException:
                pass

        welcome = find_channel(g, "welcome")
        if not welcome:
            return
        embed = discord.Embed(
            title="⚔️ A new Crusader has joined!",
            description=(f"Welcome {member.mention} to **{g.name}**!\n\n"
                         f"👉 Read the rules in {channel_link(g, 'rules')}\n"
                         f"👉 Pick your roles in {channel_link(g, 'roles')}\n"
                         f"👉 Introduce yourself in {channel_link(g, 'intro')}"),
            color=config.COLOR_WARN,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{g.member_count}")
        try:
            await welcome.send(embed=embed)
        except discord.HTTPException:
            pass

    # --- Reaction roles -------------------------------------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        # Give roles to anyone who reacted while the bot was offline.
        for guild in self.bot.guilds:
            roles_ch = find_channel(guild, "roles")
            if not roles_ch:
                continue
            try:
                async for message in roles_ch.history(limit=10):
                    for reaction in message.reactions:
                        role = self.role_for(guild, str(reaction.emoji))
                        if not role:
                            continue
                        async for user in reaction.users():
                            member = guild.get_member(user.id)
                            if member and not user.bot and role not in member.roles:
                                await member.add_roles(role, reason="Reaction role (catch-up)")
            except discord.HTTPException as e:
                print(f"  [!] Reaction role sync failed in {guild.name}: {e}", flush=True)

    def role_for(self, guild: discord.Guild, emoji: str):
        name = config.ROLE_MAP.get(emoji)
        return discord.utils.get(guild.roles, name=name) if name else None

    async def reaction_role(self, payload: discord.RawReactionActionEvent, add: bool):
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id) if guild else None
        # Only reactions in #roles count, so voting 👍 on a poll never gives roles.
        if not channel or channel != find_channel(guild, "roles"):
            return
        role = self.role_for(guild, str(payload.emoji))
        member = guild.get_member(payload.user_id)
        if not role or not member:
            return
        try:
            if add and role not in member.roles:
                await member.add_roles(role, reason="Reaction role")
            elif not add and role in member.roles:
                await member.remove_roles(role, reason="Reaction role removed")
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self.reaction_role(payload, add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self.reaction_role(payload, add=False)

    # --- /poll ----------------------------------------------------------------
    @commands.hybrid_command(description="Start a poll. Separate options with |")
    @app_commands.describe(question="What are you asking?",
                           options="Up to 10 options separated by |, e.g. Pizza | Biryani | Maggi. "
                                   "Leave empty for yes/no.")
    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.guild_only()
    async def poll(self, ctx: commands.Context, question: str, *, options: str = ""):
        choices = [o.strip() for o in options.split("|") if o.strip()]
        if len(choices) == 1 or len(choices) > 10:
            return await ctx.send("⚠️ Give 2 to 10 options separated by `|`, or none for a yes/no poll.",
                                  ephemeral=True)
        if choices:
            emojis = NUMBER_EMOJIS[:len(choices)]
            body = "\n".join(f"{e}  {c}" for e, c in zip(emojis, choices))
        else:
            emojis, body = ["👍", "👎"], "👍 Yes   ·   👎 No"

        embed = discord.Embed(title=f"📊 {question}", description=body, color=config.COLOR_MAIN)
        embed.set_footer(text=f"Poll by {ctx.author.display_name}")
        msg = await ctx.send(embed=embed)
        for e in emojis:
            await msg.add_reaction(e)

    # --- /suggest -------------------------------------------------------------
    @commands.hybrid_command(description="Suggest an idea for the server")
    @app_commands.describe(idea="Your suggestion")
    @commands.cooldown(1, 120, commands.BucketType.user)
    @commands.guild_only()
    async def suggest(self, ctx: commands.Context, *, idea: str):
        channel = find_channel(ctx.guild, "suggestions") or ctx.channel
        embed = discord.Embed(title="💡 New suggestion", description=idea[:2000], color=config.COLOR_OK)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Vote with 👍 or 👎")
        msg = await channel.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        if channel != ctx.channel:
            await ctx.send(f"✅ Posted your suggestion in {channel.mention}.", ephemeral=True)
        elif ctx.interaction:
            await ctx.send("✅ Suggestion posted.", ephemeral=True)

    # --- /report --------------------------------------------------------------
    @commands.hybrid_command(description="Privately report a member to staff")
    @app_commands.describe(member="Who you're reporting", reason="What happened")
    @commands.cooldown(2, 300, commands.BucketType.user)
    @commands.guild_only()
    async def report(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        if not ctx.interaction:
            # Delete the "!report" message so the report stays private.
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
        delivered = await mod_log(ctx.guild, "🚩 Member reported",
                      f"**Reported by:** {ctx.author.mention}\n**Member:** {member.mention} (`{member.id}`)\n"
                      f"**Channel:** {ctx.channel.mention}\n**Reason:** {reason}",
                      color=config.COLOR_BAD, important=True)
        text = REPORT_SENT if delivered else REPORT_FAILED
        if ctx.interaction:
            await ctx.send(text, ephemeral=True)
        else:
            try:
                await ctx.author.send(text)
            except discord.HTTPException:
                pass

    async def report_message(self, interaction: discord.Interaction, message: discord.Message):
        if not interaction.guild:
            return await interaction.response.send_message("Only works in a server.", ephemeral=True)
        await interaction.response.send_modal(ReportModal(message))


async def setup(bot: commands.Bot):
    await bot.add_cog(Community(bot))
