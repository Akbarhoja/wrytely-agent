import { Entry } from "@/components/entry";
import { authConfigured } from "@/lib/config";
export default function Home() {
  return <Entry configured={authConfigured()} />;
}
