import { Button, Result } from "antd";
import { Link } from "react-router-dom";
import { useDocumentTitle } from "@/shared/hooks/documentTitle";

type Props = {
  featureName: string;
  loadError?: boolean;
};

/** 与具体功能导航解耦的不可用结果视图。 */
export function FeatureUnavailableResult({
  featureName,
  loadError = false,
}: Props) {
  const title = loadError ? "暂时无法确认功能开关" : `${featureName}未启用`;
  useDocumentTitle(title);
  return (
    <Result
      status={loadError ? "warning" : "info"}
      title={title}
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
