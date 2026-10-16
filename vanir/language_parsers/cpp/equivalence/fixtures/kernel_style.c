struct packet { unsigned int length; void *data; };
static int process_packet(struct packet *packet, unsigned int limit) {
  unsigned int length = packet->length;
  if (length > limit)
    return -1;
  consume(packet->data, length);
  return 0;
}
