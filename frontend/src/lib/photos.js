// The 8 supplied photos, served from /public/photos. Mapped to design slots.
const p = (n) => `/photos/space-${n}.jpg`;

export const PHOTOS = {
  hero: p(1),
  about: [p(2), p(3), p(4)],
  spaces: { meeting: p(5), office: p(6), cowork: p(7), lounge: p(8) },
  gallery: [p(1), p(2), p(3), p(4), p(5), p(6), p(7)],
};

export default p;
