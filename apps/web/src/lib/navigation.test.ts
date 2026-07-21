import { describe, expect, it } from "vitest";
import { NAV_ITEMS, navItemsForRole } from "./navigation";

describe("navigation", () => {
  it("gives every nav item an icon component", () => {
    for (const item of NAV_ITEMS) {
      expect(item.icon).toBeDefined();
    }
  });

  it("appends the admin item, with its own icon, only for the admin role", () => {
    const memberItems = navItemsForRole("member");
    expect(memberItems.find((i) => i.to === "/admin")).toBeUndefined();

    const adminItems = navItemsForRole("admin");
    const adminItem = adminItems.find((i) => i.to === "/admin");
    expect(adminItem).toBeDefined();
    expect(adminItem?.icon).toBeDefined();
  });
});
