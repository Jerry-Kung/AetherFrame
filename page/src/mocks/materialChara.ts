import {
  type CharaProfile,
  type OfficialSeedPrompts,
  cloneOfficialSeedPrompts,
  officialSeedPromptsToApiPayload,
  toCharaProfile,
} from "@/types/material";
import * as materialApi from "@/services/materialApi";

export type SeedPromptSection = "characterSpecific" | "general" | "fixed";

/** 角色 bio 内正式种子（不含固定模板） */
export type OfficialSeedPromptSection = Exclude<SeedPromptSection, "fixed">;

/**
 * Pure update: mark one seed as `used` in a copy of official seed prompts.
 * Returns null if prompts are missing or seed id not found.
 */
export function markSeedPromptUsedInBio(
  profile: CharaProfile,
  section: OfficialSeedPromptSection,
  seedId: string
): OfficialSeedPrompts | null {
  const raw = profile.bio.officialSeedPrompts;
  if (!raw) return null;
  const next = cloneOfficialSeedPrompts(raw);
  const list = section === "characterSpecific" ? next.characterSpecific : next.general;
  const idx = list.findIndex((s) => s.id === seedId);
  if (idx === -1) return null;
  list[idx] = { ...list[idx], used: true };
  return next;
}

export type PersistMarkSeedArgs =
  | {
      characterId: string;
      profile: CharaProfile;
      section: OfficialSeedPromptSection;
      seedId: string;
    }
  | {
      section: "fixed";
      seedId: string;
    };

/** PATCH bio.official_seed_prompts 或 PATCH 固定模板；fixed 分支返回 null。 */
export async function persistMarkSeedAsUsed(args: PersistMarkSeedArgs): Promise<CharaProfile | null> {
  if (args.section === "fixed") {
    await materialApi.patchFixedSeedTemplate(args.seedId, { used: true });
    return null;
  }

  const { characterId, profile, section, seedId } = args;
  const nextSeeds = markSeedPromptUsedInBio(profile, section, seedId);
  if (!nextSeeds) {
    throw new Error("无法标记：缺少正式种子或找不到对应种子");
  }
  const detail = await materialApi.patchCharacterBio(characterId, {
    official_seed_prompts: officialSeedPromptsToApiPayload(nextSeeds),
  });
  return toCharaProfile(detail);
}

/** Alias for batch / home pages. */
export const markSeedAsUsed = persistMarkSeedAsUsed;
