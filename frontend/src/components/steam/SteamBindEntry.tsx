import { Alert, Button, Card } from "antd";

export function SteamBindEntry({
  loading,
  onBind,
}: {
  loading: boolean;
  onBind: () => void;
}) {
  return (
    <div
      style={{
        maxWidth: 560,
        margin: "0 auto",
        padding: "8px 0 48px",
      }}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="尚未绑定 Steam"
        description="绑定后可查看自己与 Steam 好友的游玩时间轴。"
      />
      <Card>
        <Button
          type="primary"
          size="large"
          block
          loading={loading}
          onClick={onBind}
        >
          绑定 Steam 账号
        </Button>
      </Card>
    </div>
  );
}
