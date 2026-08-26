import { Button, Result } from "antd";
import { Link } from "react-router-dom";

export function ForbiddenPage() {
  return (
    <Result
      status="403"
      title="没有权限"
      subTitle="此页面仅管理员可访问。"
      extra={
        <Link to="/">
          <Button type="primary">返回首页</Button>
        </Link>
      }
    />
  );
}
