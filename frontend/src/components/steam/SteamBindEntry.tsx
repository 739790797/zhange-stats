import { Alert, Button, Card } from "antd";
import { Link } from "react-router-dom";

export function SteamBindEntry({
  loading,
  onBind,
  steamConfigured,
  isAdmin = false,
}: {
  loading: boolean;
  onBind: () => void;
  /** undefined = 加载中；false = 未配置 API Key */
  steamConfigured?: boolean;
  isAdmin?: boolean;
}) {
  const notConfigured = steamConfigured === false;
  return (
    <div
      style={{
        maxWidth: 560,
        margin: "0 auto",
        padding: "8px 0 48px",
      }}
    >
      {notConfigured ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="尚未配置 Steam API Key"
          description={
            isAdmin ? (
              <span>
                请先在 <Link to="/settings/integrations">集成密钥</Link>{" "}
                填写 Steam Web API Key，再绑定账号。
              </span>
            ) : (
              "管理员尚未配置 Steam API Key，暂无法绑定。"
            )
          }
        />
      ) : (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="尚未绑定 Steam"
          description="绑定后可查看自己与 Steam 好友的游玩时间轴。"
        />
      )}
      <Card>
        <Button
          type="primary"
          size="large"
          block
          loading={loading}
          disabled={notConfigured || steamConfigured === undefined}
          onClick={onBind}
        >
          绑定 Steam 账号
        </Button>
      </Card>
    </div>
  );
}
