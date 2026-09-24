import { Alert, Button, Card, Col, Row, Spin, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { fetchMe } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { apiError, apiStatus } from "@/lib/apiError";
import { appHomePhase, type AppHomePhase } from "@/lib/appHomeSession";
import { useAuthStore } from "@/stores/authStore";

const cards = [
  {
    title: "综合查询",
    text: "逃离塔科夫的搜索还在侧栏里，首页先不承接查询。",
  },
  {
    title: "个人中心",
    text: "资料、任务、钥匙和藏身处仍从侧栏进入。",
  },
  {
    title: "本机工具",
    text: "视觉增强和辅助工具留在桌面壳，不放到这个页面。",
  },
];

export default function AppHomePage() {
  const location = useLocation();
  const setUser = useAuthStore((state) => state.setUser);
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);
  const [phase, setPhase] = useState<AppHomePhase | "checking">("checking");
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setPhase("checking");
      setError(null);
      try {
        const me = await fetchMe();
        if (cancelled) return;
        setUser(me);
        setPhase("in");
      } catch (caught) {
        if (cancelled) return;
        const next = appHomePhase(apiStatus(caught));
        if (next === "out") logout();
        setError(apiError(caught, "暂时无法确认登录状态"));
        setPhase(next);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attempt, logout, setUser]);

  if (phase === "out") {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (phase !== "in") {
    return (
      <div
        style={{
          minHeight: 280,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {phase === "checking" ? (
          <Spin size="large" />
        ) : (
          <Alert
            type="error"
            showIcon
            message="没能确认登录状态"
            description={error}
            action={
              <Button size="small" onClick={() => setAttempt((value) => value + 1)}>
                重试
              </Button>
            }
          />
        )}
      </div>
    );
  }

  const name = (user?.display_name || user?.username || "").trim();

  return (
    <>
      <PageHeader
        title="首页"
        subtitle="演示"
        extra={<Tag color="gold">演示</Tag>}
      />
      <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
        {name ? `${name}，` : ""}
        这是战鸽助手的首页，当前只是演示。启动时会先确认登录，未登录会进入登录页。
      </Typography.Paragraph>
      <Row gutter={[16, 16]}>
        {cards.map((card) => (
          <Col key={card.title} xs={24} md={8}>
            <Card title={card.title} size="small">
              {card.text}
            </Card>
          </Col>
        ))}
      </Row>
    </>
  );
}
