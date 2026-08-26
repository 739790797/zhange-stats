import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, Modal } from "antd";
import { useState } from "react";
import {
  fetchExiliumStatus,
  fetchKujiequStatus,
  fetchMihoyoStatus,
  fetchSklandStatus,
  fetchTaygedoStatus,
} from "@/api/client";
import type { MemberProfile } from "@/api/types";
import { ExiliumBindPanel } from "@/components/exilium/ExiliumBindPanel";
import { KujiequBindPanel } from "@/components/kujiequ/KujiequBindPanel";
import { MihoyoBindPanel } from "@/components/mihoyo/MihoyoBindPanel";
import { PlatformBindRow } from "@/components/profile/PlatformBindRow";
import { QqBindRow } from "@/components/profile/QqBindRow";
import { SteamBindRow } from "@/components/profile/SteamBindRow";
import { SklandBindPanel } from "@/components/skland/SklandBindPanel";
import { TaygedoBindPanel } from "@/components/taygedo/TaygedoBindPanel";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";

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
  showMihoyo: boolean;
  steamBound: boolean;
  steamConfigured?: boolean;
  isAdminUser?: boolean;
  qqBound: boolean;
  sklandBound: boolean;
  taygedoBound: boolean;
  exiliumBound: boolean;
  kujiequBound: boolean;
  mihoyoBound: boolean;
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
  unbindMihoyoPending: boolean;
  onUnbindMihoyo: () => void;
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
  showMihoyo,
  steamBound,
  steamConfigured,
  isAdminUser = false,
  qqBound,
  sklandBound,
  taygedoBound,
  exiliumBound,
  kujiequBound,
  mihoyoBound,
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
  unbindMihoyoPending,
  onUnbindMihoyo,
  invalidateProfile,
}: PlatformBindsSectionProps) {
  const queryClient = useQueryClient();
  const [sklandModalOpen, setSklandModalOpen] = useState(false);
  const [taygedoModalOpen, setTaygedoModalOpen] = useState(false);
  const [exiliumModalOpen, setExiliumModalOpen] = useState(false);
  const [kujiequModalOpen, setKujiequModalOpen] = useState(false);
  const [mihoyoModalOpen, setMihoyoModalOpen] = useState(false);

  // 角色树挂在本区（不随绑定 Modal destroyOnClose 卸载），避免「弹一下就消失」
  const sklandRoles = useRoleMembershipPicker("skland");
  const taygedoRoles = useRoleMembershipPicker("taygedo");
  const exiliumRoles = useRoleMembershipPicker("exilium");
  const kujiequRoles = useRoleMembershipPicker("kujiequ");
  const mihoyoRoles = useRoleMembershipPicker("mihoyo");

  // 本人个人中心：探测已绑定平台凭证（与签到页共用 queryKey）
  const probeSelf = !isAdminEdit;
  const sklandStatusQuery = useQuery({
    queryKey: ["skland-status"],
    queryFn: () => fetchSklandStatus(false, true),
    enabled: probeSelf && showSkland && sklandBound,
    staleTime: 60_000,
    retry: false,
  });
  const taygedoStatusQuery = useQuery({
    queryKey: ["taygedo-status"],
    queryFn: () => fetchTaygedoStatus(false, true),
    enabled: probeSelf && showTaygedo && taygedoBound,
    staleTime: 60_000,
    retry: false,
  });
  const exiliumStatusQuery = useQuery({
    queryKey: ["exilium-status"],
    queryFn: () => fetchExiliumStatus(false, true),
    enabled: probeSelf && showExilium && exiliumBound,
    staleTime: 60_000,
    retry: false,
  });
  const kujiequStatusQuery = useQuery({
    queryKey: ["kujiequ-status"],
    queryFn: () => fetchKujiequStatus(false, true),
    enabled: probeSelf && showKujiequ && kujiequBound,
    staleTime: 60_000,
    retry: false,
  });
  const mihoyoStatusQuery = useQuery({
    queryKey: ["mihoyo-status"],
    queryFn: () => fetchMihoyoStatus(false, true),
    enabled: probeSelf && showMihoyo && mihoyoBound,
    staleTime: 60_000,
    retry: false,
  });

  const sklandCredOk = !sklandBound
    ? undefined
    : sklandStatusQuery.isError
      ? false
      : sklandStatusQuery.data
        ? sklandStatusQuery.data.token_ok !== false
        : null;
  const taygedoCredOk = !taygedoBound
    ? undefined
    : taygedoStatusQuery.isError
      ? false
      : taygedoStatusQuery.data
        ? taygedoStatusQuery.data.token_ok !== false
        : null;
  const exiliumCredOk = !exiliumBound
    ? undefined
    : exiliumStatusQuery.isError
      ? false
      : exiliumStatusQuery.data
        ? exiliumStatusQuery.data.token_ok !== false
        : null;
  const kujiequCredOk = !kujiequBound
    ? undefined
    : kujiequStatusQuery.isError
      ? false
      : kujiequStatusQuery.data
        ? kujiequStatusQuery.data.token_ok !== false
        : null;
  const mihoyoCredOk = !mihoyoBound
    ? undefined
    : mihoyoStatusQuery.isError
      ? false
      : mihoyoStatusQuery.data
        ? mihoyoStatusQuery.data.token_ok !== false
        : null;

  return (
    <>
      <Card title="账号绑定" loading={isLoading && !errMsg}>
        {showSteam ? (
          <SteamBindRow
            data={data}
            steamBound={steamBound}
            steamConfigured={steamConfigured}
            isAdmin={isAdminUser}
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
            icon="skland"
            bound={sklandBound}
            credentialOk={sklandCredOk}
            errMsg={errMsg}
            unbindConfirmTitle="确认解除森空岛绑定？"
            unbindPending={unbindSklandPending}
            onOpenModal={() => setSklandModalOpen(true)}
            onOpenRoles={() => sklandRoles.openPicker()}
            onUnbind={onUnbindSkland}
          />
        ) : null}

        {!isAdminEdit && showTaygedo ? (
          <PlatformBindRow
            name="塔吉多"
            icon="taygedo"
            bound={taygedoBound}
            credentialOk={taygedoCredOk}
            errMsg={errMsg}
            borderTop
            unbindConfirmTitle="确认解除塔吉多绑定？"
            unbindPending={unbindTaygedoPending}
            onOpenModal={() => setTaygedoModalOpen(true)}
            onOpenRoles={() => taygedoRoles.openPicker()}
            onUnbind={onUnbindTaygedo}
          />
        ) : null}

        {!isAdminEdit && showKujiequ ? (
          <PlatformBindRow
            name="库街区"
            icon="kujiequ"
            bound={kujiequBound}
            credentialOk={kujiequCredOk}
            errMsg={errMsg}
            borderTop
            unbindConfirmTitle="确认解除库街区绑定？"
            unbindPending={unbindKujiequPending}
            onOpenModal={() => setKujiequModalOpen(true)}
            onOpenRoles={() => kujiequRoles.openPicker()}
            onUnbind={onUnbindKujiequ}
          />
        ) : null}

        {!isAdminEdit && showMihoyo ? (
          <PlatformBindRow
            name="米游社"
            icon="mihoyo"
            bound={mihoyoBound}
            credentialOk={mihoyoCredOk}
            errMsg={errMsg}
            borderTop
            unbindConfirmTitle="确认解除米游社绑定？"
            unbindPending={unbindMihoyoPending}
            onOpenModal={() => setMihoyoModalOpen(true)}
            onOpenRoles={() => mihoyoRoles.openPicker()}
            onUnbind={onUnbindMihoyo}
          />
        ) : null}

        {!isAdminEdit && showExilium ? (
          <PlatformBindRow
            name="追放"
            icon="exilium"
            bound={exiliumBound}
            credentialOk={exiliumCredOk}
            errMsg={errMsg}
            borderTop
            unbindConfirmTitle="确认解除追放绑定？"
            unbindPending={unbindExiliumPending}
            onOpenModal={() => setExiliumModalOpen(true)}
            onOpenRoles={() => exiliumRoles.openPicker()}
            onUnbind={onUnbindExilium}
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
            openRolePickerOnBind={false}
            onSuccess={() => {
              invalidateProfile();
              queryClient.invalidateQueries({ queryKey: ["skland-logs"] });
              setSklandModalOpen(false);
              // 下一拍再开角色树，避免与绑定 Modal 关闭抢焦点
              window.setTimeout(() => sklandRoles.openPicker(), 0);
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
            openRolePickerOnBind={false}
            onSuccess={() => {
              invalidateProfile();
              queryClient.invalidateQueries({ queryKey: ["taygedo-logs"] });
              setTaygedoModalOpen(false);
              window.setTimeout(() => taygedoRoles.openPicker(), 0);
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
            openRolePickerOnBind={false}
            onSuccess={() => {
              invalidateProfile();
              setExiliumModalOpen(false);
              window.setTimeout(() => exiliumRoles.openPicker(), 0);
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
            openRolePickerOnBind={false}
            onSuccess={() => {
              invalidateProfile();
              setKujiequModalOpen(false);
              window.setTimeout(() => kujiequRoles.openPicker(), 0);
            }}
          />
        ) : null}
      </Modal>

      <Modal
        title={mihoyoBound ? "更换米游社绑定" : "绑定米游社"}
        open={mihoyoModalOpen && !isAdminEdit}
        footer={null}
        onCancel={() => setMihoyoModalOpen(false)}
        destroyOnClose
        width={480}
      >
        {mihoyoModalOpen && !isAdminEdit ? (
          <MihoyoBindPanel
            title=""
            openRolePickerOnBind={false}
            onSuccess={() => {
              invalidateProfile();
              setMihoyoModalOpen(false);
              window.setTimeout(() => mihoyoRoles.openPicker(), 0);
            }}
          />
        ) : null}
      </Modal>

      {sklandRoles.modal}
      {taygedoRoles.modal}
      {exiliumRoles.modal}
      {kujiequRoles.modal}
      {mihoyoRoles.modal}
    </>
  );
}
