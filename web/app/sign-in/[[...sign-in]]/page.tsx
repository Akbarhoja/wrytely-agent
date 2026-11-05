import { SignIn } from "@clerk/nextjs";
import { Suspense } from "react";
import Link from "next/link";
import { authConfigured } from "@/lib/config";

export default function SignInPage() {
  return (
    <main className="auth-page">
      <Link href="/" className="brand">
        wrytely<span>↗</span>
      </Link>
      {authConfigured() ? (
        <Suspense fallback={<p>Getting sign-in ready…</p>}>
          <SignIn />
        </Suspense>
      ) : (
        <section>
          <h1>Your workspace is getting ready.</h1>
          <p>Sign-in is not connected yet. Please come back soon.</p>
          <Link href="/">Back to Wrytely</Link>
        </section>
      )}
    </main>
  );
}
