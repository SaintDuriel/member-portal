const orgs = [
  { slug: "burningman", name: "Camp Whatever" },
  { slug: "renfaire", name: "Guild Whatever" }
];

export default function HomePage() {
  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: "3rem 1rem" }}>
      <h1>Guild Sites</h1>
      <p>Select your organization to continue.</p>
      <ul>
        {orgs.map((org) => (
          <li key={org.slug}>
            <a href={`/o/${org.slug}`}>{org.name}</a>
          </li>
        ))}
      </ul>
    </main>
  );
}