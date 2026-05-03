import {
  type CharaProfile,
  type OfficialSeedPrompts,
  cloneOfficialSeedPrompts,
  officialSeedPromptsToApiPayload,
  toCharaProfile,
} from "@/types/material";
import * as materialApi from "@/services/materialApi";

export type SeedPromptSection = "characterSpecific" | "general";

/**
 * Pure update: mark one seed as `used` in a copy of official seed prompts.
 * Returns null if prompts are missing or seed id not found.
 */
export function markSeedPromptUsedInBio(
  profile: CharaProfile,
  section: SeedPromptSection,
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

export interface PersistMarkSeedArgs {
  characterId: string;
  profile: CharaProfile;
  section: SeedPromptSection;
  seedId: string;
}

/** PATCH bio.official_seed_prompts then return refreshed profile. */
export async function persistMarkSeedAsUsed({
  characterId,
  profile,
  section,
  seedId,
}: PersistMarkSeedArgs): Promise<CharaProfile> {
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
