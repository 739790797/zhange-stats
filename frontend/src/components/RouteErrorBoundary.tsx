import { Button, Result, Space, Typography } from "antd";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { reportClientError } from "@/lib/reportClientError";

type Props = {
  /** pathname 变化时清掉错误，避免卡在旧页的 Result 上。 */
  resetKey: string;
  children: ReactNode;
};

type State = {
  error: Error | null;
  resetKey: string;
  requestId: string | null;
};

export class RouteErrorBoundary extends Component<Props, State> {
  state: State;

  constructor(props: Props) {
    super(props);
    this.state = { error: null, resetKey: props.resetKey, requestId: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  static getDerivedStateFromProps(props: Props, state: State) {
    if (props.resetKey === state.resetKey) return null;
    return { error: null, resetKey: props.resetKey, requestId: null };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("route render", error, info.componentStack);
    const requestId = crypto.randomUUID?.() || String(Date.now());
    this.setState({ requestId });
    void reportClientError({
      message: error.message || "render error",
      componentStack: info.componentStack || "",
      pathname: this.props.resetKey,
      requestId,
    });
  }

  render() {
    if (this.state.error) {
      return (
        <Result
          status="error"
          title="页面出了点问题"
          subTitle={
            <Space direction="vertical" size={4}>
              <span>可以重试加载，或返回首页。</span>
              {this.state.requestId ? (
                <Typography.Text type="secondary">
                  编号 {this.state.requestId.slice(0, 8)}
                </Typography.Text>
              ) : null}
            </Space>
          }
          extra={
            <Space>
              <Button
                type="primary"
                onClick={() => this.setState({ error: null, requestId: null })}
              >
                重试
              </Button>
              <Link to="/">
                <Button>返回首页</Button>
              </Link>
            </Space>
          }
        />
      );
    }
    return this.props.children;
  }
}
