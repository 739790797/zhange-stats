import { useEffect, useRef, useState } from "react";
import { Alert, Button, Input, Modal, Space, Spin, Typography, message } from "antd";
import {
  cancelSteamCmdLogin,
  fetchSteamCmdLogin,
  startSteamCmdLogin,
  submitSteamCmdGuard,
  type SteamCmdLoginStatus,
} from "@/api/settingsApi";
import { apiError } from "@/lib/apiError";

type Props = {
  open: boolean;
  username: string;
  onClose: () => void;
  onLoggedIn: (username: string) => void;
};

const EMPTY: SteamCmdLoginStatus = { state: "idle", message: "" };

export default function SteamCmdLoginModal({ open, username, onClose, onLoggedIn }: Props) {
  const [account, setAccount] = useState(username);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState<SteamCmdLoginStatus>(EMPTY);
  const [pending, setPending] = useState(false);
  const accountRef = useRef(account);
  const finished = useRef(false);
  const started = useRef(false);
  accountRef.current = account;

  useEffect(() => {
    if (!open) return;
    setAccount(username);
    setPassword("");
    setCode("");
    setStatus(EMPTY);
    finished.current = false;
    started.current = false;
  }, [open, username]);

  useEffect(() => {
    if (!open) return;
    let stop = false;
    const tick = async () => {
      try {
        const next = await fetchSteamCmdLogin();
        if (stop || finished.current) return;
        if (next.state === "ok" && !started.current) {
          setStatus(EMPTY);
          return;
        }
        setStatus(next);
        if (next.state === "ok") {
          finished.current = true;
          message.success(next.message || "已登录");
          onLoggedIn(accountRef.current);
          onClose();
        }
      } catch (err) {
        if (!stop) message.error(apiError(err, "无法查看登录状态"));
      }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), 1000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [open, onClose, onLoggedIn]);

  async function close() {
    const active =
      status.state === "starting" || status.state === "need_guard" || status.state === "need_mobile";
    if (!finished.current && active) {
      try {
        await cancelSteamCmdLogin();
      } catch (err) {
        message.error(apiError(err, "取消登录失败"));
      }
    }
    onClose();
  }

  async function begin() {
    setPending(true);
    try {
      const next = await startSteamCmdLogin({ username: account.trim(), password });
      started.current = true;
      setPassword("");
      setStatus(next);
      if (next.state === "ok" && !finished.current) {
        finished.current = true;
        message.success(next.message || "已登录");
        onLoggedIn(accountRef.current);
        onClose();
      }
    } catch (err) {
      message.error(apiError(err, "登录失败"));
    } finally {
      setPending(false);
    }
  }

  async function sendCode() {
    setPending(true);
    try {
      const next = await submitSteamCmdGuard(code.trim());
      setCode("");
      setStatus(next);
    } catch (err) {
      message.error(apiError(err, "令牌提交失败"));
    } finally {
      setPending(false);
    }
  }

  const asking = status.state === "idle" || status.state === "error";
  return (
    <Modal
      open={open}
      title="登录 Steam"
      onCancel={() => void close()}
      destroyOnClose
      footer={
        asking ? (
          <Space>
            <Button onClick={() => void close()}>取消</Button>
            <Button type="primary" loading={pending} onClick={() => void begin()}>
              登录
            </Button>
          </Space>
        ) : status.state === "need_guard" ? (
          <Space>
            <Button onClick={() => void close()}>取消</Button>
            <Button type="primary" loading={pending} onClick={() => void sendCode()}>
              提交令牌
            </Button>
          </Space>
        ) : (
          <Button onClick={() => void close()}>取消</Button>
        )
      }
    >
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {status.state === "error" && status.message ? (
          <Alert type="error" showIcon message={status.message} />
        ) : null}
        {asking ? (
          <>
            <div>
              <Typography.Text>Steam 账号</Typography.Text>
              <Input
                value={account}
                autoComplete="off"
                placeholder="拥有雨中冒险2的 Steam 账号"
                onChange={(event) => setAccount(event.target.value)}
                style={{ marginTop: 8 }}
              />
            </div>
            <div>
              <Typography.Text>密码</Typography.Text>
              <Input.Password
                value={password}
                autoComplete="off"
                placeholder="只用于这一次登录，不会保存"
                onChange={(event) => setPassword(event.target.value)}
                style={{ marginTop: 8 }}
              />
            </div>
            <Typography.Text type="secondary">
              登录成功后，凭证留在战鸽根目录的 steamcmd 里。之后更新只使用账号，不用再填令牌。
            </Typography.Text>
          </>
        ) : null}
        {status.state === "starting" ? (
          <Space>
            <Spin />
            <Typography.Text>{status.message || "正在登录"}</Typography.Text>
          </Space>
        ) : null}
        {status.state === "need_mobile" ? (
          <Alert type="info" showIcon message={status.message || "请在手机 Steam 上允许这次登录。"} />
        ) : null}
        {status.state === "need_guard" ? (
          <div>
            <Typography.Paragraph style={{ marginBottom: 8 }}>{status.message}</Typography.Paragraph>
            <Input
              value={code}
              autoComplete="off"
              placeholder="邮箱或手机令牌"
              onChange={(event) => setCode(event.target.value)}
              onPressEnter={() => void sendCode()}
            />
          </div>
        ) : null}
      </Space>
    </Modal>
  );
}
