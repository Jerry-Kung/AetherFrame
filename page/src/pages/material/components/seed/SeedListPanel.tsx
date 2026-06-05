import { useMemo } from "react";
import type { CharaProfile, Divergence, OfficialSeedPrompts, SeedPrompt } from "@/types/material";
import type { CreativeDirectionApi } from "@/services/materialApi";
import SeedGroupSection, { type SeedGroup } from "./SeedGroupSection";

const PER_DIRECTION_LIMIT = 20;
const TOTAL_LIMIT = 100;

function countTotalSeeds(seeds: OfficialSeedPrompts): number {
  return seeds.characterSpecific.length + seeds.general.length;
}

export default function SeedListPanel({
  chara,
  directions,
  onAddBound,
  onDeleteSeed,
}: {
  chara: CharaProfile;
  directions: CreativeDirectionApi[];
  onAddBound: (directionId: string | null) => void;
  onDeleteSeed: (seed: SeedPrompt) => void;
}) {
  const seeds = useMemo(
    () =>
      chara.bio.officialSeedPrompts ?? {
        characterSpecific: [],
        general: [],
      },
    [chara.bio.officialSeedPrompts]
  );

  const groups = useMemo((): SeedGroup[] => {
    const cs = seeds.characterSpecific;
    const sortedDirs = [...directions].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    const result: SeedGroup[] = [
      {
        key: "no-direction",
        label: "默认世界观",
        items: cs.filter((s) => s.creativeDirectionId == null),
        generateBinding: null,
      },
    ];

    for (const d of sortedDirs) {
      result.push({
        key: d.id,
        label: d.title,
        directionMeta: { title: d.title, divergence: d.divergence as Divergence },
        items: cs.filter((s) => s.creativeDirectionId === d.id),
        generateBinding: d.id,
      });
    }

    result.push({
      key: "legacy-general",
      label: "通用种子（遗留）",
      items: seeds.general,
      generateBinding: undefined,
    });

    return result;
  }, [seeds, directions]);

  const totalAtLimit = countTotalSeeds(seeds) >= TOTAL_LIMIT;

  return (
    <div className="flex flex-col gap-3">
      {groups.map((g, idx) => (
        <SeedGroupSection
          key={g.key}
          group={g}
          defaultExpanded={idx < 3}
          onAddBound={onAddBound}
          onDeleteSeed={onDeleteSeed}
          perDirectionLimit={PER_DIRECTION_LIMIT}
          totalAtLimit={totalAtLimit}
        />
      ))}
    </div>
  );
}
