import { describe, expect, it } from "vitest";
import { appPath, appURL, routePath } from "@/lib/deployment-path";
import { memoResolveUrl } from "@/lib/memo-markdown";
import { parseManagedAttachmentImageURL } from "@/utils/managed-attachment";

describe("fixed deployment path", () => {
  it("builds the same OAuth callback from an origin and a canonical instance URL", () => {
    expect(appURL("/auth/callback", "https://notes.example")).toBe("https://notes.example/memo/auth/callback");
    expect(appURL("/auth/callback", "https://notes.example/memo")).toBe("https://notes.example/memo/auth/callback");
  });

  it("keeps router values relative to the app mount", () => {
    expect(routePath("/memo")).toBe("/");
    expect(routePath("/memo/memos/old")).toBe("/memos/old");
    expect(routePath("/memo-other/memos/old")).toBe("/memo-other/memos/old");
    expect(appPath("/memos/old#heading")).toBe("/memo/memos/old#heading");
  });

  it("loads stored managed attachments and legacy internal links under the mount", () => {
    const resolve = memoResolveUrl();
    expect(parseManagedAttachmentImageURL("/file/attachments/image")).toBe("image");
    expect(parseManagedAttachmentImageURL("/memo/file/attachments/image")).toBe("image");
    expect(parseManagedAttachmentImageURL("/memo/file/attachments/image?thumbnail=true")).toBeUndefined();
    expect(resolve("/file/attachments/image", "image")).toBe("/memo/file/attachments/image");
    expect(resolve("/memos/old?mode=view#section", "link")).toBe("/memo/memos/old?mode=view#section");
    expect(resolve("//example.com/memos/old", "link")).toBe("//example.com/memos/old");
    expect(resolve("javascript:alert(1)", "link")).toBeNull();
  });
});
