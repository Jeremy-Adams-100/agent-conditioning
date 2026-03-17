// Cloudflare Turnstile global type declaration
interface Window {
  turnstile?: {
    render: (
      element: HTMLElement,
      options: {
        sitekey: string;
        callback: (token: string) => void;
        theme?: "light" | "dark" | "auto";
      }
    ) => void;
  };
}
