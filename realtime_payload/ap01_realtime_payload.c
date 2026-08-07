/*
 * AP01 local two-page quota loader.
 *
 * This payload is linked directly into an unused, zero-filled tail of the
 * shortened first pet GIF resource.  It deliberately has no writable global
 * state and no C library dependency.  The synchronous stock weather request
 * owns a stack download_state while webclient_perform invokes quota_sink.
 * Completion is published through a small tmpfs metadata file.  The LVGL
 * one-second timer consumes that metadata on the UI thread.
 *
 * There is no verified rename() entry point in firmware 1.0.2_0031.  Three
 * tmpfs generations plus an applied ACK provide the same atomicity without
 * guessing an ABI.  The worker never truncates either the last published slot
 * or the slot currently acknowledged by LVGL, closes the third slot, and only
 * then publishes a checksummed metadata record.
 *
 * The UI deliberately keeps at most one 320x240 GIF decoder active.  The
 * stock weather page (window 5) gets one new Kimi+DeepSeek GIF object, the
 * stock pet page (window 7) reuses its original GIF object for Codex+Claude,
 * and the unselected object points at a 1x1 tmpfs placeholder.  Every source
 * change is followed by the stock center-alignment call so a placeholder-born
 * object cannot expand from the page center into the adjacent settings page.
 */

typedef unsigned char u8;
typedef unsigned int u32;

#define ATTR_ENTRY __attribute__((section(".text.entry"), noinline, used))
#define ATTR_NOINLINE __attribute__((noinline))

/* Verified firmware 1.0.2_0031 entry points. */
#define VA_STOCK_UI_TIMER                 0xa00bb5dau
#define VA_OBJ_GET_CHILD                  0xa00c5d84u
#define VA_OBJ_GET_CHILD_COUNT            0xa00c5fe4u
#define VA_OBJ_ALIGN_TO                   0xa00c3876u
#define VA_GIF_CREATE                     0xa01930feu
#define VA_LV_GIF_SET_SRC                 0xa00cf8d8u
#define VA_WEBCLIENT_PERFORM              0xa00d86bau
#define VA_OPEN                           0xa003f448u
#define VA_CLOSE                          0xa0026788u
#define VA_READ                           0xa003f5f4u
#define VA_WRITE                          0xa0027d94u

/* AP01/NuttX open flags recovered from stock call sites. */
#define AP01_O_RDONLY                     1
#define AP01_O_RDWR_CREAT_TRUNC           39
#define AP01_MODE_0666                    438

#define ERR_IO                            (-5)
#define ERR_INVAL                         (-22)
#define ERR_FBIG                          (-27)

#define GIF_MAX_BYTES                     (256u * 1024u)
#define GIF_MIN_BYTES                     13u
#define PAGE_COUNT                        2u
#define WEATHER_WINDOW_INDEX              5u
#define PET_WINDOW_INDEX                  7u
#define BUNDLE_HEADER_BYTES               20u
#define BUNDLE_MAGIC                      0x42325041u /* "AP2B" */
#define BUNDLE_VERSION                    1u
#define BUNDLE_SALT                       0xa50102b2u
#define PAGE_NONE                         0xffffffffu
#define THEME_SELECTED_PAGE_OFFSET        52u

#define META_MAGIC                        0x46494751u /* "QGIF" little endian */
#define META_SALT                         0xa501a501u
#define META_GENERATION_MASK              0x7fffffffu
#define UI_MAGIC                          0x49553241u /* "A2UI" */
#define UI_SALT                           0x5a01225au

/* Runtime-only idle counters used by j_update_screen_saver.  Resetting the
 * counters leaves the user's persisted ScreenSave/ScreenOff settings intact.
 */
#define RAM_SCREEN_SAVER_COUNTER          0x62fcc1e4u
#define RAM_SCREEN_OFF_COUNTER            0x62fcc1e8u

/* Exact webclient_context offsets for this 32-bit build. */
#define WEBCLIENT_SINK_ARG_OFFSET         64u
#define WEBCLIENT_HTTP_STATUS_OFFSET      96u

typedef void (*void_one_arg_fn)(void *);
typedef void *(*obj_get_child_fn)(void *, int);
typedef u32 (*obj_get_child_count_fn)(void *);
typedef void (*obj_align_to_fn)(void *, void *, int, int, int);
typedef void *(*gif_create_fn)(void *, void *, const void *);
typedef void (*gif_set_src_fn)(void *, const void *);
typedef int (*webclient_perform_fn)(void *);
typedef int (*open_fn)(const char *, int, int);
typedef int (*close_fn)(int);
typedef int (*io_fn)(int, void *, u32);
typedef int (*write_fn)(int, const void *, u32);

struct quota_meta
{
  u32 magic;
  u32 generation;
  u32 slot;
  u32 check;
};

struct bundle_header
{
  u32 magic;
  u32 version;
  u32 size[PAGE_COUNT];
  u32 check;
};

struct quota_ui_state
{
  u32 magic;
  u32 theme;
  u32 gif[PAGE_COUNT];
  u32 active_page;
  u32 generation;
  u32 slot;
  u32 check;
};

struct download_state
{
  int fd[PAGE_COUNT];
  u32 expected[PAGE_COUNT];
  u32 written[PAGE_COUNT];
  u32 gif_header_len[PAGE_COUNT];
  u8 gif_header[PAGE_COUNT][10];
  u8 last_byte[PAGE_COUNT];
  struct bundle_header bundle;
  u32 bundle_header_len;
  u32 page;
  u32 slot;
  u32 generation;
};

static const char quota_slot0_main[] = "/tmp/.ap01p0m.gif";
static const char quota_slot0_others[] = "/tmp/.ap01p0o.gif";
static const char quota_slot1_main[] = "/tmp/.ap01p1m.gif";
static const char quota_slot1_others[] = "/tmp/.ap01p1o.gif";
static const char quota_slot2_main[] = "/tmp/.ap01p2m.gif";
static const char quota_slot2_others[] = "/tmp/.ap01p2o.gif";
static const char quota_meta_path[] = "/tmp/.ap01q.meta";
static const char quota_ack_path[] = "/tmp/.ap01q.ack";
static const char quota_ui_path[] = "/tmp/.ap01q.ui";
static const char placeholder_path[] = "/tmp/.ap01blank.gif";

/* Minimal, opaque black 1x1 GIF89a.  It exists only to make lv_gif_set_src
 * release the previous full-size decoder without relying on a NULL-source ABI.
 */
static const u8 placeholder_gif[] = {
  0x47u, 0x49u, 0x46u, 0x38u, 0x39u, 0x61u, 0x01u, 0x00u,
  0x01u, 0x00u, 0x80u, 0x00u, 0x00u, 0x00u, 0x00u, 0x00u,
  0xffu, 0xffu, 0xffu, 0x21u, 0xf9u, 0x04u, 0x00u, 0x00u,
  0x00u, 0x00u, 0x00u, 0x2cu, 0x00u, 0x00u, 0x00u, 0x00u,
  0x01u, 0x00u, 0x01u, 0x00u, 0x00u, 0x02u, 0x02u, 0x44u,
  0x01u, 0x00u, 0x3bu
};

static ATTR_NOINLINE int fw_open(const char *path, int flags, int mode)
{
  return ((open_fn)VA_OPEN)(path, flags, mode);
}

static ATTR_NOINLINE int fw_close(int fd)
{
  return ((close_fn)VA_CLOSE)(fd);
}

static ATTR_NOINLINE int fw_read(int fd, void *buffer, u32 length)
{
  return ((io_fn)VA_READ)(fd, buffer, length);
}

static ATTR_NOINLINE int fw_write(int fd, const void *buffer, u32 length)
{
  return ((write_fn)VA_WRITE)(fd, buffer, length);
}

/* AP2B transport order is stable: page 0 is Codex+Claude (main) and page 1 is
 * Kimi+DeepSeek (others).  Keep this separate from the physical window order.
 */
static const char *bundle_page_slot_path(u32 slot, u32 page)
{
  if (slot == 0u)
    {
      return page == 0u ? quota_slot0_main : quota_slot0_others;
    }

  if (slot == 1u)
    {
      return page == 0u ? quota_slot1_main : quota_slot1_others;
    }

  return page == 0u ? quota_slot2_main : quota_slot2_others;
}

/* Physical window 5 replaces weather with Kimi+DeepSeek; physical window 7
 * keeps the proven stock pet GIF object for Codex+Claude.
 */
static const char *window_page_slot_path(u32 slot, u32 window_page)
{
  return bundle_page_slot_path(slot, window_page == 0u ? 1u : 0u);
}

static u32 meta_check(const struct quota_meta *meta)
{
  return meta->magic ^ meta->generation ^ meta->slot ^ META_SALT;
}

static int meta_valid(const struct quota_meta *meta)
{
  return meta->magic == META_MAGIC &&
         meta->generation != 0u &&
         meta->generation <= META_GENERATION_MASK &&
         meta->slot <= 2u &&
         meta->check == meta_check(meta);
}

static ATTR_NOINLINE int read_exact(int fd, void *buffer, u32 length)
{
  u8 *cursor = (u8 *)buffer;
  u32 done = 0u;

  while (done < length)
    {
      int amount = fw_read(fd, cursor + done, length - done);
      if (amount <= 0 || (u32)amount > length - done)
        {
          return ERR_IO;
        }

      done += (u32)amount;
    }

  return 0;
}

static ATTR_NOINLINE int write_all(int fd, const void *buffer, u32 length)
{
  const u8 *cursor = (const u8 *)buffer;
  u32 done = 0u;

  while (done < length)
    {
      int amount = fw_write(fd, cursor + done, length - done);
      if (amount <= 0 || (u32)amount > length - done)
        {
          return ERR_IO;
        }

      done += (u32)amount;
    }

  return 0;
}

static ATTR_NOINLINE int read_record(const char *path, struct quota_meta *meta)
{
  int fd = fw_open(path, AP01_O_RDONLY, 0);
  int result;

  if (fd < 0)
    {
      return ERR_IO;
    }

  result = read_exact(fd, meta, (u32)sizeof(*meta));
  if (fw_close(fd) < 0)
    {
      result = ERR_IO;
    }

  if (result < 0 || !meta_valid(meta))
    {
      return ERR_INVAL;
    }

  return 0;
}

static ATTR_NOINLINE int write_record(const char *path, u32 generation,
                                      u32 slot)
{
  struct quota_meta meta;
  int fd;
  int result;

  meta.magic = META_MAGIC;
  meta.generation = generation;
  meta.slot = slot;
  meta.check = meta_check(&meta);

  fd = fw_open(path, AP01_O_RDWR_CREAT_TRUNC, AP01_MODE_0666);
  if (fd < 0)
    {
      return ERR_IO;
    }

  result = write_all(fd, &meta, (u32)sizeof(meta));
  if (fw_close(fd) < 0)
    {
      result = ERR_IO;
    }

  return result;
}

static int read_meta(struct quota_meta *meta)
{
  return read_record(quota_meta_path, meta);
}

static int read_ack(struct quota_meta *meta)
{
  return read_record(quota_ack_path, meta);
}

static int publish_meta(u32 generation, u32 slot)
{
  return write_record(quota_meta_path, generation, slot);
}

static int publish_ack(u32 generation, u32 slot)
{
  return write_record(quota_ack_path, generation, slot);
}

static u32 ui_check(const struct quota_ui_state *state)
{
  return state->magic ^ state->theme ^ state->gif[0] ^ state->gif[1] ^
         state->active_page ^ state->generation ^ state->slot ^ UI_SALT;
}

static int ui_valid(const struct quota_ui_state *state, void *theme)
{
  return state->magic == UI_MAGIC && state->theme == (u32)theme &&
         state->gif[0] != 0u && state->gif[1] != 0u &&
         (state->active_page == PAGE_NONE || state->active_page < PAGE_COUNT) &&
         state->generation <= META_GENERATION_MASK && state->slot <= 2u &&
         state->check == ui_check(state);
}

static ATTR_NOINLINE int read_ui_state(struct quota_ui_state *state,
                                       void *theme)
{
  int fd = fw_open(quota_ui_path, AP01_O_RDONLY, 0);
  int result;

  if (fd < 0)
    {
      return ERR_IO;
    }

  result = read_exact(fd, state, (u32)sizeof(*state));
  if (fw_close(fd) < 0)
    {
      result = ERR_IO;
    }

  if (result < 0 || !ui_valid(state, theme))
    {
      return ERR_INVAL;
    }

  return 0;
}

static ATTR_NOINLINE int write_ui_state(struct quota_ui_state *state,
                                        void *theme)
{
  int fd;
  int result;

  state->magic = UI_MAGIC;
  state->theme = (u32)theme;
  state->check = ui_check(state);

  fd = fw_open(quota_ui_path, AP01_O_RDWR_CREAT_TRUNC, AP01_MODE_0666);
  if (fd < 0)
    {
      return ERR_IO;
    }

  result = write_all(fd, state, (u32)sizeof(*state));
  if (fw_close(fd) < 0)
    {
      result = ERR_IO;
    }

  return result;
}

static u32 bundle_check(const struct bundle_header *header)
{
  return header->magic ^ header->version ^ header->size[0] ^
         header->size[1] ^ BUNDLE_SALT;
}

static int bundle_header_valid(const struct bundle_header *header)
{
  u32 page;

  if (header->magic != BUNDLE_MAGIC || header->version != BUNDLE_VERSION ||
      header->check != bundle_check(header))
    {
      return 0;
    }

  for (page = 0u; page < PAGE_COUNT; ++page)
    {
      if (header->size[page] < GIF_MIN_BYTES ||
          header->size[page] > GIF_MAX_BYTES)
        {
          return 0;
        }
    }

  return 1;
}

static int gif_header_valid(const u8 *header)
{
  int version_ok;

  version_ok = header[0] == (u8)'G' &&
               header[1] == (u8)'I' &&
               header[2] == (u8)'F' &&
               header[3] == (u8)'8' &&
               header[4] == (u8)'9' &&
               header[5] == (u8)'a';

  return version_ok &&
         header[6] == 0x40u && header[7] == 0x01u && /* 320 */
         header[8] == 0xf0u && header[9] == 0x00u;   /* 240 */
}

/* NuttX webclient_sink_callback_t ABI. */
ATTR_ENTRY int ap01_quota_sink(char **buffer, int offset, int datend,
                               int *buflen, void *argument)
{
  struct download_state *state = (struct download_state *)argument;
  const u8 *chunk;
  u32 length;
  u32 index;
  u32 amount;
  u32 remaining;
  u32 page;
  u32 source_index;

  if (state == (void *)0 || buffer == (void *)0 || *buffer == (void *)0 ||
      buflen == (void *)0 || offset < 0 || datend < offset ||
      *buflen < 0 || datend > *buflen)
    {
      return ERR_INVAL;
    }

  length = (u32)(datend - offset);
  if (length == 0u)
    {
      return 0;
    }

  chunk = (const u8 *)(*buffer) + (u32)offset;
  index = 0u;
  while (index < length)
    {
      if (state->bundle_header_len < BUNDLE_HEADER_BYTES)
        {
          ((u8 *)&state->bundle)[state->bundle_header_len++] = chunk[index++];
          if (state->bundle_header_len == BUNDLE_HEADER_BYTES)
            {
              const struct bundle_header *header = &state->bundle;

              if (!bundle_header_valid(header))
                {
                  return ERR_INVAL;
                }

              for (page = 0u; page < PAGE_COUNT; ++page)
                {
                  state->expected[page] = header->size[page];
                }
            }

          continue;
        }

      page = state->page;
      if (page >= PAGE_COUNT || state->fd[page] < 0 ||
          state->written[page] > state->expected[page])
        {
          return ERR_FBIG;
        }

      remaining = state->expected[page] - state->written[page];
      amount = length - index;
      if (amount > remaining)
        {
          amount = remaining;
        }

      if (amount == 0u)
        {
          state->page++;
          continue;
        }

      source_index = 0u;
      while (state->gif_header_len[page] < 10u && source_index < amount)
        {
          state->gif_header[page][state->gif_header_len[page]++] =
            chunk[index + source_index];
          source_index++;
        }

      if (state->gif_header_len[page] == 10u &&
          !gif_header_valid(state->gif_header[page]))
        {
          return ERR_INVAL;
        }

      if (write_all(state->fd[page], chunk + index, amount) < 0)
        {
          return ERR_IO;
        }

      state->written[page] += amount;
      state->last_byte[page] = chunk[index + amount - 1u];
      index += amount;

      if (state->written[page] == state->expected[page])
        {
          state->page++;
        }
    }

  return 0;
}

/* Replacement for the HTTP-path call to webclient_perform(ctx). */
ATTR_ENTRY int ap01_quota_webclient_wrapper(void *context)
{
  struct download_state state;
  struct quota_meta old_meta;
  struct quota_meta old_ack;
  u32 next_generation;
  u32 next_slot;
  u32 have_meta;
  u32 have_ack;
  u32 page;
  int perform_result;
  int close_result;

  if (context == (void *)0)
    {
      return ERR_INVAL;
    }

  have_meta = read_meta(&old_meta) == 0 ? 1u : 0u;
  have_ack = read_ack(&old_ack) == 0 ? 1u : 0u;

  if (have_meta != 0u)
    {
      next_generation = (old_meta.generation + 1u) & META_GENERATION_MASK;
      if (next_generation == 0u)
        {
          next_generation = 1u;
        }
    }
  else
    {
      next_generation = 1u;
    }

  /* Exclude both the decoder's acknowledged slot and the last published slot
   * that the UI may adopt concurrently.  Three slots guarantee a free one.
   */
  for (next_slot = 0u; next_slot < 3u; ++next_slot)
    {
      if ((have_meta == 0u || next_slot != old_meta.slot) &&
          (have_ack == 0u || next_slot != old_ack.slot))
        {
          break;
        }
    }

  if (next_slot >= 3u)
    {
      return ERR_IO;
    }

  state.bundle_header_len = 0u;
  state.page = 0u;
  state.slot = next_slot;
  state.generation = next_generation;
  for (page = 0u; page < PAGE_COUNT; ++page)
    {
      state.fd[page] = -1;
      state.expected[page] = 0u;
      state.written[page] = 0u;
      state.gif_header_len[page] = 0u;
      state.last_byte[page] = 0u;
    }

  for (page = 0u; page < PAGE_COUNT; ++page)
    {
      state.fd[page] = fw_open(bundle_page_slot_path(next_slot, page),
                               AP01_O_RDWR_CREAT_TRUNC, AP01_MODE_0666);
      if (state.fd[page] < 0)
        {
          while (page > 0u)
            {
              page--;
              (void)fw_close(state.fd[page]);
              state.fd[page] = -1;
            }

          return ERR_IO;
        }
    }

  /* Stock code already installs ap01_quota_sink at +60.  Supplying the
   * per-request stack state at +64 makes the callback re-entrant and avoids
   * an unverified writable global address.
   */
  *(void **)((u8 *)context + WEBCLIENT_SINK_ARG_OFFSET) = &state;
  perform_result = ((webclient_perform_fn)VA_WEBCLIENT_PERFORM)(context);
  *(void **)((u8 *)context + WEBCLIENT_SINK_ARG_OFFSET) = (void *)0;

  close_result = 0;
  for (page = 0u; page < PAGE_COUNT; ++page)
    {
      if (fw_close(state.fd[page]) < 0)
        {
          close_result = ERR_IO;
        }

      state.fd[page] = -1;
    }

  if (perform_result < 0)
    {
      return perform_result;
    }

  if (*(u32 *)((u8 *)context + WEBCLIENT_HTTP_STATUS_OFFSET) != 200u ||
      close_result < 0)
    {
      return ERR_IO;
    }

  if (state.bundle_header_len != BUNDLE_HEADER_BYTES ||
      state.page != PAGE_COUNT)
    {
      return ERR_INVAL;
    }

  for (page = 0u; page < PAGE_COUNT; ++page)
    {
      if (state.written[page] != state.expected[page] ||
          state.gif_header_len[page] != 10u ||
          !gif_header_valid(state.gif_header[page]) ||
          state.last_byte[page] != 0x3bu)
        {
          return ERR_INVAL;
        }
    }

  if (publish_meta(state.generation, state.slot) < 0)
    {
      return ERR_IO;
    }

  return 0;
}

static void reset_idle_counters(void)
{
  *(volatile u32 *)RAM_SCREEN_SAVER_COUNTER = 0u;
  *(volatile u32 *)RAM_SCREEN_OFF_COUNTER = 0u;
}

static ATTR_NOINLINE int ensure_placeholder(void)
{
  int fd;
  int result;

  fd = fw_open(placeholder_path, AP01_O_RDWR_CREAT_TRUNC, AP01_MODE_0666);
  if (fd < 0)
    {
      return ERR_IO;
    }

  result = write_all(fd, placeholder_gif, (u32)sizeof(placeholder_gif));
  if (fw_close(fd) < 0)
    {
      result = ERR_IO;
    }

  return result;
}

/* The original single-page loader proved this stock object chain on firmware
 * 1.0.2_0031: window+16 -> wrapper, wrapper+4 -> state, state[0] -> GIF.
 * Reusing it avoids allocating a second full-size decoder for page 7.
 */
static void *stock_gif_from_window(void *window)
{
  void *wrapper;
  void *state;

  if (window == (void *)0)
    {
      return (void *)0;
    }

  wrapper = *(void **)((u8 *)window + 16u);
  if (wrapper == (void *)0)
    {
      return (void *)0;
    }

  state = *(void **)((u8 *)wrapper + 4u);
  if (state == (void *)0)
    {
      return (void *)0;
    }

  return *(void **)state;
}

static u32 selected_quota_page(void *theme)
{
  u32 selected = *(u32 *)((u8 *)theme + THEME_SELECTED_PAGE_OFFSET);

  if (selected == WEATHER_WINDOW_INDEX)
    {
      return 0u;
    }

  return selected == PET_WINDOW_INDEX ? 1u : PAGE_NONE;
}

static int set_gif_source(void *gif, const char *source)
{
  ((gif_set_src_fn)VA_LV_GIF_SET_SRC)(gif, source);
  /* In this LVGL build gif+0x5c is the decoder descriptor. */
  return *(void **)((u8 *)gif + 0x5cu) != (void *)0 ? 0 : ERR_IO;
}

static void center_gif_on_window(void *gif, void *window)
{
  ((obj_align_to_fn)VA_OBJ_ALIGN_TO)(gif, window, 9, 0, 0);
}

static ATTR_NOINLINE int lookup_quota_windows(void *theme, void **window)
{
  u32 count;

  if (theme == (void *)0 || window == (void *)0)
    {
      return ERR_INVAL;
    }

  count = ((obj_get_child_count_fn)VA_OBJ_GET_CHILD_COUNT)(theme);
  if (count <= PET_WINDOW_INDEX)
    {
      return ERR_INVAL;
    }

  /* Stock child creation labels and the observed encoder order agree on this
   * cycle: settings 6 -> pet 7 -> weather 5 -> date 4 -> time 3 -> power 0.
   * Window 6 is settings and must remain untouched.  The saved child ownership
   * is revalidated every UI tick.
   */
  window[0] = ((obj_get_child_fn)VA_OBJ_GET_CHILD)(
    theme, (int)WEATHER_WINDOW_INDEX);
  window[1] = ((obj_get_child_fn)VA_OBJ_GET_CHILD)(
    theme, (int)PET_WINDOW_INDEX);
  if (window[0] == (void *)0 || window[1] == (void *)0)
    {
      return ERR_INVAL;
    }

  return 0;
}

static ATTR_NOINLINE int ui_objects_valid(
  const struct quota_ui_state *ui, void *theme, void **window)
{
  u32 child;
  u32 count;
  int found;

  if (!ui_valid(ui, theme))
    {
      return 0;
    }

  /* A checksummed pointer record alone is insufficient: the stock UI can
   * destroy and recreate whole themes.  Weather window 5 owns our direct
   * child; pet window 7 must still resolve to the stock GIF through the proven
   * internal chain.
   */
  count = ((obj_get_child_count_fn)VA_OBJ_GET_CHILD_COUNT)(window[0]);
  found = 0;
  for (child = 0u; child < count; ++child)
    {
      if (((obj_get_child_fn)VA_OBJ_GET_CHILD)(window[0], (int)child) ==
          (void *)ui->gif[0])
        {
          found = 1;
          break;
        }
    }

  if (found == 0 || stock_gif_from_window(window[1]) != (void *)ui->gif[1])
    {
      return 0;
    }

  return 1;
}

static ATTR_NOINLINE int initialize_quota_pages(
  void *theme, void **window, struct quota_ui_state *ui)
{
  void *stock_gif;

  /* Add one placeholder-backed child to stock weather window 5 and reuse the
   * original pet window 7 GIF.  Do not append a slider child and never write
   * theme+52; that field is the stock encoder's current selected page index.
   */
  if (ensure_placeholder() < 0)
    {
      return ERR_IO;
    }

  stock_gif = stock_gif_from_window(window[1]);
  if (stock_gif == (void *)0 || set_gif_source(stock_gif, placeholder_path) < 0)
    {
      return ERR_IO;
    }
  center_gif_on_window(stock_gif, window[1]);

  /* Do not mutate either stock window's flags.  Firmware 1.0.2_0031 address
   * 0xa00c1400 is lv_obj_add_flag (not lv_obj_clear_flag); passing flag 1
   * there hides the complete slider page and was the cause of the earlier
   * two-page white-screen build.
   */
  ui->gif[0] = (u32)((gif_create_fn)VA_GIF_CREATE)(
    window[0], window[0], placeholder_path);
  ui->gif[1] = (u32)stock_gif;
  if (ui->gif[0] == 0u ||
      *(void **)((u8 *)ui->gif[0] + 0x5cu) == (void *)0)
    {
      return ERR_IO;
    }

  ui->active_page = PAGE_NONE;
  ui->generation = 0u;
  ui->slot = 0u;
  return write_ui_state(ui, theme);
}

static ATTR_NOINLINE int apply_selected_page(
  void *theme, const struct quota_meta *meta, struct quota_ui_state *ui,
  void **window)
{
  u32 desired = selected_quota_page(theme);
  u32 old_active = ui->active_page;

  if (old_active < PAGE_COUNT && old_active != desired)
    {
      if (set_gif_source((void *)ui->gif[old_active], placeholder_path) < 0)
        {
          return ERR_IO;
        }
      center_gif_on_window((void *)ui->gif[old_active], window[old_active]);
      ui->active_page = PAGE_NONE;
    }

  if (desired < PAGE_COUNT &&
      (ui->active_page != desired || ui->generation != meta->generation ||
       ui->slot != meta->slot))
    {
      /* The old full decoder has already been released above.  When refreshing
       * the same page, lv_gif_set_src releases its old source before opening
       * the new generation, so peak full-size decoder count remains one.
       */
      if (set_gif_source((void *)ui->gif[desired],
                         window_page_slot_path(meta->slot, desired)) < 0)
        {
          (void)set_gif_source((void *)ui->gif[desired], placeholder_path);
          center_gif_on_window((void *)ui->gif[desired], window[desired]);
          ui->active_page = PAGE_NONE;
          ui->generation = 0u;
          ui->slot = 0u;
          (void)write_ui_state(ui, theme);
          return ERR_IO;
        }
      center_gif_on_window((void *)ui->gif[desired], window[desired]);
      ui->active_page = desired;
    }

  if (desired == PAGE_NONE)
    {
      ui->active_page = PAGE_NONE;
    }

  ui->generation = meta->generation;
  ui->slot = meta->slot;
  if (write_ui_state(ui, theme) < 0)
    {
      return ERR_IO;
    }

  return publish_ack(meta->generation, meta->slot);
}

/* Replacement callback pointer for the stock one-second LVGL timer. */
ATTR_ENTRY void ap01_quota_ui_timer_wrapper(void *timer)
{
  struct quota_meta meta;
  struct quota_meta ack;
  struct quota_ui_state ui;
  void *theme;
  void *window[PAGE_COUNT];
  u32 desired;

  reset_idle_counters();

  ((void_one_arg_fn)VA_STOCK_UI_TIMER)(timer);

  reset_idle_counters();

  if (timer == (void *)0 || read_meta(&meta) < 0)
    {
      return;
    }

  theme = *(void **)((u8 *)timer + 12u);
  if (theme == (void *)0)
    {
      return;
    }

  if (lookup_quota_windows(theme, window) < 0)
    {
      return;
    }

  if (read_ui_state(&ui, theme) < 0 ||
      !ui_objects_valid(&ui, theme, window))
    {
      if (initialize_quota_pages(theme, window, &ui) < 0)
        {
          return;
        }
    }

  desired = selected_quota_page(theme);
  if (read_ack(&ack) == 0 && ack.generation == meta.generation &&
      ack.slot == meta.slot && ui.active_page == desired &&
      ui.generation == meta.generation && ui.slot == meta.slot)
    {
      return;
    }

  (void)apply_selected_page(theme, &meta, &ui, window);
}
