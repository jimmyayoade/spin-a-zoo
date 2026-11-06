# Spin-a-Zoo

A spin-and-match board game for 2–4 players, made for [Batocera](https://batocera.org)'s Pygame system.

Spin your spinner, cover a matching square on the zoo board, and be the first to get **4 in a row**.

## Rules

**Setup:** each player picks a tile color (green, blue, yellow or red, 16 tiles each) and a seat (N, E, S or W). Empty seats keep their spinners: they still get passed around. The board is shuffled for every game.

The board is a 5×5 grid. Every square has a color, a pattern, a shape and an animal:

| Spinner | Values |
|---|---|
| Color | green, blue, purple, red, yellow |
| Shape | square, star, circle, triangle, hexagon |
| Pattern | musical notes, stripes, polka dots, zigzag, leaves |
| Animal | German shepherd, tuxedo cat, eagle, lion, bear |

Each value appears once in every row and every column, and no two squares share the same pair of features.

Each spinner has 8 sections: its 5 values, 2 **Wild** and 1 **Spin A Zoo!**

**On your turn, spin:**

| Result | What you do |
|---|---|
| A value | Play a tile on an **empty** square that matches. If no empty square matches, play on any empty square. You can't play on a square that already has a tile. |
| **Wild** | Play on any square, even on top of another tile, as long as the stack has fewer than 4. |
| **Spin A Zoo!** | Everyone passes their spinner clockwise (including the empty seats' spinners), then you spin again. |

Then it's the next player's turn, clockwise.

**Win:** be the first to get 4 of your tiles in a row: across, down or diagonally. Only the top tile of a stack counts.

**No winner:** if every square has a tile and nobody has won, PLAY AGAIN! A player with no tiles left skips their turns; if nobody has tiles left, play again.

## License

MIT
