"use client";

import { UserButton, useUser } from "@clerk/nextjs";
import { Workspace } from "./workspace";

function SignedEntry() {
  const { isLoaded, isSignedIn, user } = useUser();
  if (!isLoaded) return <Workspace mode="loading" />;
  if (!isSignedIn || !user) return <Workspace mode="signed-out" />;
  return (
    <Workspace
      key={user.id}
      mode="signed-in"
      userId={user.id}
      name={user.firstName || "there"}
      account={<UserButton />}
    />
  );
}
export function Entry({ configured }: { configured: boolean }) {
  return configured ? <SignedEntry /> : <Workspace mode="unconfigured" />;
}
