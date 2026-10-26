#include <sys/epoll.h>
#include <unistd.h>
#include <stdio.h>
#include <assert.h>
/* Linux-only real readiness experiment: leave unread bytes in a pipe. */
static int probe(int flags) {
    int fds[2];assert(pipe(fds)==0);int ep=epoll_create1(0);assert(ep>=0);
    struct epoll_event event={0},out={0};event.events=EPOLLIN|flags;event.data.fd=fds[0];
    assert(epoll_ctl(ep,EPOLL_CTL_ADD,fds[0],&event)==0);assert(write(fds[1],"abc",3)==3);
    assert(epoll_wait(ep,&out,1,200)==1);char c;assert(read(fds[0],&c,1)==1);
    int repeat=epoll_wait(ep,&out,1,100);close(ep);close(fds[0]);close(fds[1]);return repeat;
}
int main(void) {
    int lt=probe(0),et=probe(EPOLLET);assert(lt==1);assert(et==0);
    printf("{\"level_trigger_repeats_while_unread\":%d,\"edge_trigger_no_new_edge\":%d}\n",lt,et);
    return 0;
}
