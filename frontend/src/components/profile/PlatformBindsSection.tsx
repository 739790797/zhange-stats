import { useQueryClient } from "@tanstack/react-query";
import { Card, Modal } from "antd";
import { useState } from "react";
import type { MemberProfile } from "@/api/types";
import { ExiliumBindPanel } from "@/components/ExiliumBindPanel";
import { KujiequBindPanel } from "@/components/KujiequBindPanel";
import { PlatformBindRow } from "@/components/profile/PlatformBindRow";
import { QqBindRow } from "@/components/profile/QqBindRow";
import { SteamBindRow } from "@/components/profile/SteamBindRow";
import { SklandBindPanel } from "@/components/SklandBindPanel";
import { TaygedoBindPanel } from "@/components/TaygedoBindPanel";

type PlatformBindsSectionProps = {
  isLoading: boolean;
  errMsg: string | null;
  isAdminEdit: boolean;
  data: MemberProfile | undefined;
  showSteam: boolean;
  showSkland: boolean;
  showTaygedo: boolean;
  showExilium: boolean;
  showKujiequ: boolean;
  steamBound: boolean;
  qqBound: boolean;
  sklandBound: boolean;
  taygedoBound: boolean;
  exiliumBound: boolean;
  kujiequBound: boolean;
  startSteamBindPending: boolean;
  unbindSteamPending: boolean;
  onStartSteamBind: () => void;
  onUnbindSteam: () => void;
  startQqBindPending: boolean;
  unbindQqPending: boolean;
  onStartQqBind: () => void;
  onUnbindQq: () => void;
  unbindSklandPending: boolean;
  onUnbindSkland: () => void;
  unbindTaygedoPending: boolean;
  onUnbindTaygedo: () => void;
  unbindExiliumPending: boolean;
  onUnbindExilium: () => void;
  unbindKujiequPending: boolean;
  onUnbindKujiequ: () => void;
  invalidateProfile: () => void;
};

export function PlatformBindsSection({
  isLoading,
  errMsg,
  isAdminEdit,
  data,
  showSteam,
  showSkland,
  showTaygedo,
  showExilium,
  showKujiequ,
  steamBound,
  qqBound,
  sklandBound,
  taygedoBound,
  exiliumBound,
  kujiequBound,
  startSteamBindPending,
  unbindSteamPending,
  onStartSteamBind,
  onUnbindSteam,
  startQqBindPending,
  unbindQqPending,
  onStartQqBind,
  onUnbindQq,
  unbindSklandPending,
  onUnbindSkland,
  unbindTaygedoPending,
  onUnbindTaygedo,
  unbindExiliumPending,
  onUnbindExilium,
  unbindKujiequPending,
  onUnbindKujiequ,
  invalidateProfile,
}: PlatformBindsSectionProps) {
  const queryClient = useQueryClient();
  const [sklandModalOpen, setSklandModalOpen] = useState(false);
  const [taygedoModalOpen, setTaygedoModalOpen] = useState(false);
  const [exiliumModalOpen, setExiliumModalOpen] = useState(false);
  const [kujiequModalOpen, setKujiequModalOpen] = useState(false);

  return (
    <>
      <Card title="账号绑定" loading={isLoading && !errMsg}>
        {showSteam ? (
          <SteamBindRow
            data={data}
            steamBound={steamBound}
            errMsg={errMsg}
            startBindPending={startSteamBindPending}
            unbindPending={unbindSteamPending}
            onStartBind={onStartSteamBind}
            onUnbind={onUnbindSteam}
          />
        ) : null}

        <QqBindRow
          data={data}
          qqBound={qqBound}
          errMsg={errMsg}
          startBindPending={startQqBindPending}
          unbindPending={unbindQqPending}
          onStartBind={onStartQqBind}
          onUnbind={onUnbindQq}
        />

        {!isAdminEdit && showSkland ? (
          <PlatformBindRow
            name="森空岛"
            bound={sklandBound}
            errMsg={errMsg}
            unbindConfirmTitle="确认解除森空岛绑定？"
            unbindPending={unbindSklandPending}
            onOpenModal={() => setSklandModalOpen(true)}
            onUnbind={onUnbindSkland}
          />
        ) : null}

        {!isAdminEdit && showTaygedo ? (
          <PlatformBindRow
            name="塔吉多"
            bound={taygedoBound}
            errMsg={errMsg}
            borderTop
            unbindConfirmTitle="确认解除塔吉多绑定？"
            unbindPending={unbindTaygedoPending}
            onOpenModal={() => setTaygedoModalOpen(true)}
            onUnbind={onUnbindTaygedo}
          />
        ) : null}

        {!isAdminEdit && showExilium ? (
          <PlatformBindRow
            name="追放"
            bound={exiliumBound}
            errMsg={errMsg}
            borderTop
            unbindConfirmTitle="确认解除追放社区绑定？"
            unbindPending={unbindExiliumPending}
            onOpenModal={() => setExiliumModalOpen(true)}
            onUnbind={onUnbindExilium}
          />
        ) : null}

        {!isAdminEdit && showKujiequ ? (
          <PlatformBindRow
            name="库街区"
            bound={kujiequBound}
            errMsg={errMsg}
            borderTop
            unbindConfirmTitle="确认解除库街区绑定？"
            unbindPending={unbindKujiequPending}
            onOpenModal={() => setKujiequModalOpen(true)}
            onUnbind={onUnbindKujiequ}
          />
        ) : null}
      </Card>

      <Modal
        title={sklandBound ? "更换森空岛绑定" : "绑定森空岛"}
        open={sklandModalOpen && !isAdminEdit}
        footer={null}
        onCancel={() => setSklandModalOpen(false)}
        destroyOnClose
        width={480}
      >
        {sklandModalOpen && !isAdminEdit ? (
          <SklandBindPanel
            title=""
            onSuccess={() => {
              invalidateProfile();
              queryClient.invalidateQueries({ queryKey: ["skland-logs"] });
              setSklandModalOpen(false);
            }}
          />
        ) : null}
      </Modal>

      <Modal
        title={taygedoBound ? "更换塔吉多绑定" : "绑定塔吉多"}
        open={taygedoModalOpen && !isAdminEdit}
        footer={null}
        onCancel={() => setTaygedoModalOpen(false)}
        destroyOnClose
        width={480}
      >
        {taygedoModalOpen && !isAdminEdit ? (
          <TaygedoBindPanel
            title=""
            onSuccess={() => {
              invalidateProfile();
              queryClient.invalidateQueries({ queryKey: ["taygedo-logs"] });
              setTaygedoModalOpen(false);
            }}
          />
        ) : null}
      </Modal>

      <Modal
        title={exiliumBound ? "更换追放绑定" : "绑定追放"}
        open={exiliumModalOpen && !isAdminEdit}
        footer={null}
        onCancel={() => setExiliumModalOpen(false)}
        destroyOnClose
        width={480}
      >
        {exiliumModalOpen && !isAdminEdit ? (
          <ExiliumBindPanel
            title=""
            onSuccess={() => {
              invalidateProfile();
              setExiliumModalOpen(false);
            }}
          />
        ) : null}
      </Modal>

      <Modal
        title={kujiequBound ? "更换库街区绑定" : "绑定库街区"}
        open={kujiequModalOpen && !isAdminEdit}
        footer={null}
        onCancel={() => setKujiequModalOpen(false)}
        destroyOnClose
        width={480}
      >
        {kujiequModalOpen && !isAdminEdit ? (
          <KujiequBindPanel
            title=""
            onSuccess={() => {
              invalidateProfile();
              setKujiequModalOpen(false);
            }}
          />
        ) : null}
      </Modal>
    </>
  );
}
