import { useState } from "react";
import { Segmented } from "antd";
import { SklandGameEventsPanel } from "@/features/platforms/skland/components/skland/SklandGameEventsPanel";
import { EndfieldOperatorInfoPage } from "./EndfieldOperatorInfoPage";

type Pane = "calendar" | "operators";
type Props = { enabled: boolean };

export function EndfieldBoxPanel({ enabled }: Props) {
  const [pane, setPane] = useState<Pane>("calendar");

  return (
    <div>
      <Segmented
        style={{ marginBottom: 16 }}
        value={pane}
        options={[
          { label: "活动日历", value: "calendar" as const },
          { label: "干员信息", value: "operators" as const },
        ]}
        onChange={(value) => setPane(value as Pane)}
      />
      {pane === "calendar" ? (
        <SklandGameEventsPanel game="endfield" />
      ) : (
        <EndfieldOperatorInfoPage enabled={enabled} />
      )}
    </div>
  );
}
