import { Button, Result } from "antd";
import { Link } from "react-router-dom";
import { GUIDE_NAV, flattenGuideLeaves } from "@/lib/guideNav";
import { PLATFORM_NAV } from "@/lib/platformFeatures";

function featureLabel(featureId: string): string {
  const platform = PLATFORM_NAV.find((item) => item.featureId === featureId);
  if (platform) return platform.label;
  const guide = flattenGuideLeaves(GUIDE_NAV).find(
    (item) => item.featureId === featureId,
  );
  return guide?.label || "该功能";
}

export function FeatureUnavailablePage({
  featureId,
  loadError = false,
}: {
  featureId: string;
  loadError?: boolean;
}) {
  const name = featureLabel(featureId);
  return (
    <Result
      status={loadError ? "warning" : "info"}
      title={loadError ? "暂时无法确认功能开关" : `${name}未启用`}
      subTitle={
        loadError
          ? "请稍后重试。若持续出现，请联系管理员。"
          : "管理员已关闭此功能。可返回首页使用其他入口。"
      }
      extra={
        <Link to="/">
          <Button type="primary">返回首页</Button>
        </Link>
      }
    />
  );
}
