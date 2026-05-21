import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Taiji Sandbox',
  description: 'Invitation-only ephemeral AI runtime demo starter kit'
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
