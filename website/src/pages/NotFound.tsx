import { Link } from "react-router-dom";
import Seo from "@/components/Seo";

const NotFound = () => {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted">
      <Seo title="404 | SSMaker" description="페이지를 찾을 수 없습니다." path="/404" noIndex />
      <div className="text-center">
        <h1 className="mb-4 text-4xl font-bold">404</h1>
        <p className="mb-4 text-xl text-muted-foreground">페이지를 찾을 수 없습니다.</p>
        <Link to="/" className="text-primary underline hover:text-primary/90">
          홈으로 돌아가기
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
