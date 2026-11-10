"""Game rule migration (1.21.11, 25w44a).

Game rules became registry entries, so ``/gamerule`` now takes a namespaced
snake_case id.  Several rules were also renamed to match the "Edit Game Rules"
menu, and three of them have inverted meaning.
"""

from __future__ import annotations

import re

# old camelCase -> new registry path (without "minecraft:")
RENAMES = {
    "announceAdvancements": "show_advancement_messages",
    "commandBlocksEnabled": "command_blocks_work",
    "commandModificationBlockLimit": "max_block_modifications",
    "disableElytraMovementCheck": "elytra_movement_check",
    "disablePlayerMovementCheck": "player_movement_check",
    "disableRaids": "raids",
    "doDaylightCycle": "advance_time",
    "doEntityDrops": "entity_drops",
    "doImmediateRespawn": "immediate_respawn",
    "doInsomnia": "spawn_phantoms",
    "doLimitedCrafting": "limited_crafting",
    "doMobLoot": "mob_drops",
    "doMobSpawning": "spawn_mobs",
    "doPatrolSpawning": "spawn_patrols",
    "doTileDrops": "block_drops",
    "doTraderSpawning": "spawn_wandering_traders",
    "doVinesSpread": "spread_vines",
    "doWardenSpawning": "spawn_wardens",
    "doWeatherCycle": "advance_weather",
    "maxCommandChainLength": "max_command_sequence_length",
    "maxCommandForkCount": "max_command_forks",
    "naturalRegeneration": "natural_health_regeneration",
    "snowAccumulationHeight": "max_snow_accumulation_height",
    "spawnRadius": "respawn_radius",
    "spawnerBlocksEnabled": "spawner_blocks_work",
    # regular camelCase -> snake_case renames
    "blockExplosionDropDecay": "block_explosion_drop_decay",
    "commandBlockOutput": "command_block_output",
    "drowningDamage": "drowning_damage",
    "enderPearlsVanishOnDeath": "ender_pearls_vanish_on_death",
    "fallDamage": "fall_damage",
    "fireDamage": "fire_damage",
    "forgiveDeadPlayers": "forgive_dead_players",
    "freezeDamage": "freeze_damage",
    "globalSoundEvents": "global_sound_events",
    "keepInventory": "keep_inventory",
    "lavaSourceConversion": "lava_source_conversion",
    "logAdminCommands": "log_admin_commands",
    "maxEntityCramming": "max_entity_cramming",
    "minecartMaxSpeed": "max_minecart_speed",
    "mobExplosionDropDecay": "mob_explosion_drop_decay",
    "mobGriefing": "mob_griefing",
    "playersNetherPortalCreativeDelay": "players_nether_portal_creative_delay",
    "playersNetherPortalDefaultDelay": "players_nether_portal_default_delay",
    "playersSleepingPercentage": "players_sleeping_percentage",
    "projectilesCanBreakBlocks": "projectiles_can_break_blocks",
    "randomTickSpeed": "random_tick_speed",
    "reducedDebugInfo": "reduced_debug_info",
    "sendCommandFeedback": "send_command_feedback",
    "showDeathMessages": "show_death_messages",
    "spawnMonsters": "spawn_monsters",
    "spectatorsGenerateChunks": "spectators_generate_chunks",
    "tntExplosionDropDecay": "tnt_explosion_drop_decay",
    "tntExplodes": "tnt_explodes",
    "universalAnger": "universal_anger",
    "waterSourceConversion": "water_source_conversion",
    "pvp": "pvp",
    "locatorBar": "locator_bar",
}

INVERTED = {"disableElytraMovementCheck", "disablePlayerMovementCheck", "disableRaids"}

_RULE = re.compile(r"\bgamerule\s+([A-Za-z_][A-Za-z0-9_:]*)(\s+(true|false))?")

_CAMEL = re.compile(r"(?<=[a-z0-9])([A-Z])")


def camel_to_snake(name: str) -> str:
    return _CAMEL.sub(lambda m: "_" + m.group(1).lower(), name)


def rewrite(line: str, ctx, path: str = "") -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name.startswith("minecraft:") or "_" in name:
            return match.group(0)
        new_path = RENAMES.get(name)
        if new_path is None:
            new_path = camel_to_snake(name)
            ctx.warn(f"unknown game rule '{name}', guessed minecraft:{new_path}", path)
        tail = match.group(2) or ""
        if name in INVERTED and match.group(3):
            value = "false" if match.group(3) == "true" else "true"
            tail = " " + value
        ctx.change("gamerule.registry_id", path, f"{name} -> minecraft:{new_path}")
        return f"gamerule minecraft:{new_path}{tail}"

    return _RULE.sub(replace, line)
